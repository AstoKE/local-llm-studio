import asyncio
import platform
import shutil
import psutil

async def system_snapshot() -> dict:
    memory = psutil.virtual_memory()
    gpu = None
    if shutil.which('nvidia-smi'):
        try:
            process = await asyncio.create_subprocess_exec(
                'nvidia-smi', '--query-gpu=name,utilization.gpu,memory.used,memory.total',
                '--format=csv,noheader,nounits', stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL)
            try:
                output, _ = await asyncio.wait_for(process.communicate(), timeout=2)
            except TimeoutError:
                process.kill()
                await process.wait()
                raise
            if process.returncode == 0:
                gpu = []
                for line in output.decode().strip().splitlines():
                    name, utilization, used, total = [part.strip() for part in line.split(',')]
                    gpu.append(dict(name=name, utilization=float(utilization), memory_used_mib=float(used), memory_total_mib=float(total)))
        except (OSError, ValueError, TimeoutError):
            gpu = None
    return dict(cpu_percent=psutil.cpu_percent(), cpu_count=psutil.cpu_count(),
                memory_used=memory.used, memory_total=memory.total, memory_percent=memory.percent,
                platform=platform.system(), gpu=gpu, gpu_note=None if gpu else 'GPU telemetry unavailable; CPU and RAM metrics remain available.')
