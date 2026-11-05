"""Requires installed backend dependencies; uses an isolated migrated SQLite DB."""
import os
import tempfile
import unittest

class APITests(unittest.TestCase):
    def test_migrated_database_and_provider_outage(self):
        # Run in a subprocess so cached configuration cannot leak between tests.
        import subprocess
        import sys
        with tempfile.TemporaryDirectory() as directory:
            env = dict(os.environ, STUDIO_DATABASE_URL=f'sqlite:///{directory}/test.db', STUDIO_OLLAMA_URL='http://127.0.0.1:1')
            subprocess.run([sys.executable, '-m', 'alembic', 'upgrade', 'head'], env=env, check=True)
            code = '''
from fastapi.testclient import TestClient
from backend.main import app
with TestClient(app) as client:
    assert client.get('/api/health').json()['database'] == 'connected'
    assert client.get('/api/models').status_code == 503
    dashboard = client.get('/api/dashboard')
    assert dashboard.status_code == 200
    assert dashboard.json()['ollama']['models'] is None
    assert dashboard.json()['system']['memory_total'] > 0
'''
            subprocess.run([sys.executable, '-c', code], env=env, check=True)
