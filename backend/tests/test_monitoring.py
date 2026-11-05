import asyncio
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
import tempfile
import unittest
from unittest.mock import AsyncMock, patch
from sqlalchemy import select
# Never touch the application database, including when this module runs alone.
_database = tempfile.TemporaryDirectory(prefix='studio-monitoring-test-')
os.environ['STUDIO_DATABASE_URL'] = f'sqlite:///{_database.name}/test.db'

from backend.database.session import Base, engine, SessionLocal
from backend.models.entities import InferenceRun, SystemSample
from backend.services.monitoring import MetricsSampler, run_dict, save_run, save_sample
from backend.services.system import gpu_snapshot, parse_nvidia, sysfs_gpus

class InlineIOTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        async def inline(function, *args, **kwargs):
            return function(*args, **kwargs)
        p = patch('asyncio.to_thread', side_effect=inline)
        p.start()
        self.addCleanup(p.stop)

class DeviceTests(InlineIOTests):
    async def test_nvidia_partial_values_preserve_unknown_and_multiple_devices(self):
        rows = parse_nvidia('gpu-1, GPU One, 00000000:01:00.0, 52, 1024, 8192\ngpu-2, GPU Two, 00000000:02:00.0, [N/A], N/A, 4096\n')
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]['memory_used_mib'], 1024)
        self.assertIsNone(rows[1]['utilization'])
        self.assertIsNone(rows[1]['memory_used_mib'])

    async def test_amd_and_intel_partial_sysfs_without_vendor_tools(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for card, vendor in [('card0','0x1002'),('card1','0x8086')]:
                device = root/card/'device'
                device.mkdir(parents=True)
                (device/'vendor').write_text(vendor)
            (root/'card0'/'device'/'gpu_busy_percent').write_text('37')
            (root/'card0'/'device'/'mem_info_vram_used').write_text(str(1024**3))
            # Fake card/device paths need distinct PCI identifiers as real sysfs symlinks have.
            with patch('backend.services.system.Path.resolve', side_effect=[Path('0000:01:00.0'),Path('0000:02:00.0')]):
                rows = sysfs_gpus(root)
            self.assertEqual(len(rows), 2)
            self.assertEqual(rows[0]['utilization'],37)
            self.assertEqual(rows[0]['memory_used_mib'],1024)
            self.assertIsNone(rows[1]['utilization'])
            self.assertIsNone(rows[1]['memory_total_mib'])

    async def test_cpu_only_and_subprocess_permission_fallback(self):
        with patch('backend.services.system.shutil.which', return_value=None), patch('backend.services.system.sysfs_gpus', return_value=[]):
            self.assertIsNone(await gpu_snapshot())
        with patch('backend.services.system.shutil.which', return_value='/usr/bin/nvidia-smi'), patch('backend.services.system.asyncio.create_subprocess_exec', side_effect=PermissionError), patch('backend.services.system.sysfs_gpus', return_value=[]):
            self.assertIsNone(await gpu_snapshot())

    async def test_gpu_timeout_kills_process(self):
        process = AsyncMock()
        process.kill = unittest.mock.Mock()
        async def timeout(awaitable, timeout):
            awaitable.close()
            raise TimeoutError
        with patch('backend.services.system.shutil.which', return_value='nvidia-smi'), patch('backend.services.system.asyncio.create_subprocess_exec', return_value=process), patch('backend.services.system.asyncio.wait_for', side_effect=timeout), patch('backend.services.system.sysfs_gpus', return_value=[]):
            self.assertIsNone(await gpu_snapshot())
        process.kill.assert_called_once()
        process.wait.assert_awaited_once()

class HistoryTests(InlineIOTests):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        Base.metadata.drop_all(engine)
        Base.metadata.create_all(engine)

    async def test_retention_and_provider_rate_no_fabrication(self):
        with SessionLocal.begin() as session:
            session.add(SystemSample(created_at=datetime.now(timezone.utc)-timedelta(days=9),payload={}))
        save_sample({'sampled_at':datetime.now(timezone.utc).isoformat(),'cpu_percent':10})
        with SessionLocal() as session:
            self.assertEqual(len(session.scalars(select(SystemSample)).all()),1)
        save_run('a','fixture','playground',{'status':'completed','eval_count':12,'eval_duration':2000000000})
        save_run('b','fixture','chat',{'status':'interrupted'})
        with SessionLocal() as session:
            rows = session.scalars(select(InferenceRun).order_by(InferenceRun.id)).all()
            self.assertEqual(run_dict(rows[0])['tokens_per_second'],6)
            self.assertIsNone(run_dict(rows[1])['tokens_per_second'])
            self.assertNotIn('content',rows[0].statistics)

    async def test_sampler_persists_without_browser_and_survives_storage_failure(self):
        sampler = MetricsSampler()
        measurement = {'sampled_at':datetime.now(timezone.utc).isoformat(),'cpu_percent':12}
        with patch('backend.services.monitoring.system_snapshot', return_value=measurement):
            await sampler.sample()
        with SessionLocal() as session:
            self.assertEqual(len(session.scalars(select(SystemSample)).all()),1)
        with patch('backend.services.monitoring.system_snapshot', return_value=measurement), patch('backend.services.monitoring.save_sample', side_effect=OSError('disk full')), self.assertLogs('backend.services.monitoring',level='ERROR'):
            await sampler.sample()
        self.assertIsNotNone(sampler.error)
        self.assertEqual(sampler.latest['cpu_percent'],12)
