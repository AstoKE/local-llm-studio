import asyncio
import csv
import math
import platform
import shutil
from datetime import datetime, timezone
from pathlib import Path
import psutil


def number(value: str) -> float | None:
    try:
        result = float(value)
        return result if math.isfinite(result) and result >= 0 else None
    except ValueError:
        return None


def parse_nvidia(output: str) -> list[dict]:
    devices = []
    for row in csv.reader(output.splitlines()):
        if len(row) != 6:
            continue
        identifier, name, pci, utilization, used, total = [part.strip() for part in row]
        devices.append(dict(id=identifier, name=name, pci=pci.lower(), source='nvidia-smi',
                            utilization=number(utilization), memory_used_mib=number(used), memory_total_mib=number(total)))
    return devices


def sysfs_gpus(root: Path = Path('/sys/class/drm')) -> list[dict]:
    devices = []
    seen: set[str] = set()
    for card in sorted(root.glob('card[0-9]*')):
        if not card.name[4:].isdigit():
            continue
        device = card / 'device'
        try:
            pci = device.resolve().name
            if pci in seen:
                continue
            vendor = (device / 'vendor').read_text().strip().lower()
            vendor_name = {'0x1002': 'AMD', '0x8086': 'Intel', '0x10de': 'NVIDIA'}.get(vendor, 'GPU')
            seen.add(pci)
            def read(filename: str) -> float | None:
                try:
                    return number((device / filename).read_text().strip())
                except OSError:
                    return None
            used, total = read('mem_info_vram_used'), read('mem_info_vram_total')
            devices.append(dict(id=pci, pci=pci, name=f'{vendor_name} ({pci})', source='sysfs',
                                utilization=read('gpu_busy_percent'),
                                memory_used_mib=used / 1024**2 if used is not None else None,
                                memory_total_mib=total / 1024**2 if total is not None else None))
        except OSError:
            continue
    return devices


async def gpu_snapshot() -> list[dict] | None:
    devices = []
    if shutil.which('nvidia-smi'):
        try:
            process = await asyncio.create_subprocess_exec(
                'nvidia-smi', '--query-gpu=uuid,name,pci.bus_id,utilization.gpu,memory.used,memory.total',
                '--format=csv,noheader,nounits', stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL)
            try:
                output, _ = await asyncio.wait_for(process.communicate(), timeout=2)
            except (TimeoutError, asyncio.CancelledError):
                try:
                    process.kill()
                except ProcessLookupError:
                    pass
                await process.wait()
                raise
            if process.returncode == 0:
                devices = parse_nvidia(output.decode(errors='replace'))
        except (OSError, ValueError, TimeoutError):
            pass
    # Prefer NVIDIA utility measurements, add other devices from read-only kernel interfaces.
    fallback = await asyncio.to_thread(sysfs_gpus)
    def normalize(pci: str) -> str:
        parts = pci.lower().split(':')
        if len(parts) == 3:
            try:
                return f'{int(parts[0], 16):04x}:{parts[1]}:{parts[2]}'
            except ValueError:
                pass
        return pci.lower()
    known = {normalize(g['pci']) for g in devices}
    devices.extend(g for g in fallback if normalize(g['pci']) not in known)
    return devices or None


async def system_snapshot() -> dict:
    cpu, gpu = await asyncio.gather(asyncio.to_thread(psutil.cpu_percent, 0.1), gpu_snapshot())
    memory = psutil.virtual_memory()
    return dict(sampled_at=datetime.now(timezone.utc).isoformat(), cpu_percent=cpu, cpu_count=psutil.cpu_count(),
                memory_used=memory.used, memory_available=memory.available, memory_total=memory.total, memory_percent=memory.percent,
                platform=platform.system(), gpu=gpu,
                gpu_note='GPU fields are null where the driver exposes no measurement.' if gpu else 'GPU telemetry unavailable; CPU and RAM metrics remain available.')
