"""Deployment generation tests: no systemd, trust store, network or real .env writes."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

module_path=Path(__file__).resolve().parents[2]/'scripts/deploy_lan.py'
spec=importlib.util.spec_from_file_location('studio_deploy_lan',module_path)
deployment=importlib.util.module_from_spec(spec)
spec.loader.exec_module(deployment)

class DeploymentTests(unittest.TestCase):
    def test_only_private_ipv4_and_unprivileged_gateway_ports(self):
        for value in ['192.168.1.20','10.0.0.5','172.16.4.8']:
            self.assertEqual(deployment.private_address(value),value)
        for value in ['127.0.0.1','0.0.0.0','8.8.8.8','192.0.2.1','::1','192.168.1.1;echo bad']:
            with self.assertRaises(ValueError):
                deployment.private_address(value)
        for port in [443,2019,3000,8000,11434,65536]:
            with self.assertRaises(ValueError):
                deployment.render(Path('/tmp/studio'),'192.168.1.20',port,'/usr/bin','/usr/bin/caddy')

    def test_generated_services_preserve_local_application_and_private_gateway(self):
        files=deployment.render(Path('/tmp/studio'),'192.168.1.20',8443,'/opt/node/bin:/usr/bin','/usr/bin/caddy')
        self.assertIn('https://192.168.1.20:8443',files['Caddyfile'])
        self.assertIn('bind 192.168.1.20',files['Caddyfile'])
        self.assertIn('reverse_proxy 127.0.0.1:3000',files['Caddyfile'])
        self.assertIn('skip_install_trust',files['Caddyfile'])
        self.assertIn('admin off',files['Caddyfile'])
        self.assertNotIn('0.0.0.0','\n'.join(files.values()))
        self.assertIn('/opt/node/bin:/usr/bin',files['local-llm-studio-web.service'])
        self.assertIn('--production',files['local-llm-studio-web.service'])
        self.assertIn('XDG_DATA_HOME=',files['local-llm-studio-gateway.service'])

    def test_env_updates_preserve_existing_secrets_comments_and_database(self):
        original='# keep\nSTUDIO_ADMIN_TOKEN=secret$unchanged\nSTUDIO_DATABASE_URL=sqlite:///data/studio.db\nSTUDIO_LAN_MODE=false\nexport STUDIO_LAN_MODE=false\n'
        result=deployment.update_env(original,{'STUDIO_LAN_MODE':'true','STUDIO_WEB_ORIGIN':'https://192.168.1.20:8443'})
        self.assertIn('STUDIO_ADMIN_TOKEN=secret$unchanged',result)
        self.assertIn('STUDIO_DATABASE_URL=sqlite:///data/studio.db',result)
        self.assertIn('# keep',result)
        self.assertEqual(result.count('STUDIO_LAN_MODE='),1)

    def test_staging_never_changes_env_or_installs_services(self):
        import os
        cwd=Path.cwd()
        try:
            with tempfile.TemporaryDirectory() as directory:
                root=Path(directory)
                (root/'.env').write_text('STUDIO_ADMIN_TOKEN=keep\n')
                with patch.object(deployment,'ROOT',root),patch('sys.argv',['deploy_lan.py','--address','192.168.1.20']),patch.object(deployment.subprocess,'run',side_effect=AssertionError('No process in staging')),contextlib.redirect_stdout(io.StringIO()):
                    deployment.main()
                self.assertEqual((root/'.env').read_text(),'STUDIO_ADMIN_TOKEN=keep\n')
                profile=json.loads((root/'deploy/generated/lan/profile.json').read_text())
                self.assertEqual(profile['origin'],'https://192.168.1.20:8443')
                self.assertEqual((root/'deploy/generated/lan/profile.json').stat().st_mode&0o777,0o600)
        finally:
            os.chdir(cwd)

    def test_missing_dependency_fails_before_mutation(self):
        import os
        cwd=Path.cwd()
        try:
            with tempfile.TemporaryDirectory() as directory:
                root=Path(directory)
                (root/'.env').write_text('KEEP=unchanged\n')
                with patch.object(deployment,'ROOT',root),patch('sys.argv',['deploy_lan.py','--address','192.168.1.20','--apply']),patch.object(deployment,'required_program',side_effect=RuntimeError('caddy missing')),patch.object(deployment.os,'geteuid',return_value=1000):
                    with self.assertRaisesRegex(RuntimeError,'caddy missing'):
                        deployment.main()
                self.assertEqual((root/'.env').read_text(),'KEEP=unchanged\n')
                self.assertFalse((root/'deploy/generated').exists())
                with patch.object(deployment,'ROOT',root),patch('sys.argv',['deploy_lan.py','--address','192.168.1.20','--apply']),patch.object(deployment.os,'geteuid',return_value=0):
                    with self.assertRaisesRegex(RuntimeError,'not with sudo'):
                        deployment.main()
        finally:
            os.chdir(cwd)

    def test_private_writes_reject_symlinks_and_control_characters(self):
        with tempfile.TemporaryDirectory() as directory:
            target=Path(directory)/'target'
            target.write_text('unchanged')
            alias=Path(directory)/'alias'
            alias.symlink_to(target)
            with self.assertRaises(ValueError):
                deployment.write_private(alias,'replacement')
            self.assertEqual(target.read_text(),'unchanged')
        with self.assertRaises(ValueError):
            deployment.quoted('path\nExecStart=bad')
