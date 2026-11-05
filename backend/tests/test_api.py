"""ASGI integration tests with isolated SQLite and deterministic provider fixtures."""
import os
import tempfile
import unittest
from unittest.mock import patch

_database = tempfile.TemporaryDirectory()
os.environ['STUDIO_DATABASE_URL'] = f'sqlite:///{_database.name}/test.db'
os.environ['STUDIO_WEB_ORIGIN'] = 'http://127.0.0.1:3000'
os.environ['STUDIO_ADMIN_TOKEN'] = 'test-only-token-with-at-least-32-characters'

import httpx
from backend.main import app
from backend.database.session import Base, engine
from backend.models import entities
from backend.providers.ollama import OllamaProvider
from backend.services.chat import active_conversations, active_jobs

class APITests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        # Run fixture SQLite operations inline; sandbox disallows event-loop thread wakeups.
        async def inline(function, *args, **kwargs):
            return function(*args, **kwargs)
        self.thread_patch = patch('asyncio.to_thread', side_effect=inline)
        self.thread_patch.start()
        self.addCleanup(self.thread_patch.stop)
        Base.metadata.drop_all(engine)
        Base.metadata.create_all(engine)
        self.requests = []
        def handle(request):
            import json
            self.requests.append((request.url.path, json.loads(request.content) if request.content else None))
            if request.url.path == '/api/chat':
                return httpx.Response(200, text='{"message":{"content":"Hello "},"done":false}\n{"message":{"content":"world"},"done":true,"eval_count":2,"eval_duration":1000000000}\n')
            if request.url.path == '/api/pull':
                return httpx.Response(200, text='{"status":"downloading","total":100,"completed":50}\n{"status":"success"}\n')
            return httpx.Response(200, json={})
        self.upstream = httpx.AsyncClient(base_url='http://runtime', transport=httpx.MockTransport(handle))
        app.state.provider = OllamaProvider(self.upstream)
        self.client = httpx.AsyncClient(base_url='http://127.0.0.1', transport=httpx.ASGITransport(app=app))

    async def asyncTearDown(self):
        await self.client.aclose()
        await self.upstream.aclose()
        active_conversations.clear()
        active_jobs.clear()

    async def create(self):
        r = await self.client.post('/api/conversations', json={'model': 'fixture', 'title': 'Test'})
        self.assertEqual(r.status_code, 201, r.text)
        return r.json()['id']

    async def test_saved_chat_edit_regenerate_and_delete(self):
        cid = await self.create()
        body = {'model': 'fixture', 'content': 'Hi', 'conversation_id': cid}
        r = await self.client.post('/api/chat', json=body)
        self.assertEqual(r.status_code, 200)
        self.assertIn('Hello ', r.text)
        self.assertIn('"type": "done"', r.text)
        detail = (await self.client.get(f'/api/conversations/{cid}')).json()
        self.assertEqual([m['content'] for m in detail['messages']], ['Hi', 'Hello world'])
        self.assertEqual(detail['messages'][1]['statistics']['eval_count'], 2)
        r = await self.client.post('/api/chat', json={**body, 'content': '', 'regenerate': True})
        self.assertEqual(r.status_code, 200)
        r = await self.client.post('/api/chat', json={**body, 'content': 'Edited', 'edit_message_id': detail['messages'][0]['id']})
        self.assertEqual(r.status_code, 200)
        detail = (await self.client.get(f'/api/conversations/{cid}')).json()
        self.assertEqual([m['content'] for m in detail['messages']], ['Edited', 'Hello world'])
        self.assertFalse(active_jobs)
        self.assertFalse(active_conversations)
        await self.client.delete(f'/api/conversations/{cid}')
        self.assertEqual((await self.client.get(f'/api/conversations/{cid}')).status_code, 404)

    async def test_admin_protection_origin_and_input_validation(self):
        for action in ['pull', 'delete', 'load', 'unload']:
            self.assertEqual((await self.client.post(f'/api/models/{action}', json={'model': 'fixture'})).status_code, 401)
        r = await self.client.post('/api/models/pull', json={'model': 'fixture'}, headers={'Authorization': f"Bearer {os.environ['STUDIO_ADMIN_TOKEN']}"})
        self.assertIn('success', r.text)
        self.assertEqual((await self.client.post('/api/chat', json={'model':'fixture','content':'x','configuration':{'options':{'frequency_penalty':1}}})).status_code, 422)
        self.assertEqual((await self.client.post('/api/conversations', json={'model':'fixture'}, headers={'Origin':'https://evil.invalid'})).status_code, 403)
        self.assertEqual((await self.client.post('/api/conversations', json={'model':'fixture'}, headers={'Origin':'http://127.0.0.1:3000'})).status_code, 201)
        self.assertEqual((await self.client.post('/api/conversations', json={'model':'invalid model!'})).status_code, 422)

    async def test_playground_does_not_persist_and_presets_roundtrip(self):
        r = await self.client.post('/api/chat', json={'model':'fixture','content':'Hello'})
        self.assertIn('"type": "done"', r.text)
        self.assertEqual((await self.client.get('/api/conversations')).json(), [])
        r = await self.client.post('/api/presets', json={'name':'Test', 'configuration':{'options':{'temperature':0.2}}})
        self.assertEqual(r.status_code, 201)
        self.assertEqual((await self.client.get('/api/presets')).json()[0]['configuration']['options']['temperature'], 0.2)

    async def test_disconnect_saves_partial_output_and_releases_job(self):
        from backend.schemas.inference import ChatInput
        from backend.services.chat import generate, prepare_chat
        cid = await self.create()
        body = ChatInput(model='fixture', content='Hi', conversation_id=cid)
        history = prepare_chat(body)
        active_conversations.add(cid)
        active_jobs.add('job')
        generator = generate(app.state.provider, body, history, 'job')
        self.assertIn('token', await anext(generator))
        await generator.aclose()
        detail = (await self.client.get(f'/api/conversations/{cid}')).json()
        self.assertEqual(detail['messages'][-1]['statistics']['status'], 'interrupted')
        self.assertFalse(active_jobs)
        self.assertFalse(active_conversations)

    async def test_model_defaults_and_explicit_playground_snapshot(self):
        r = await self.client.put('/api/model-preferences?model=fixture', json={'options': {'temperature': 0.3}})
        self.assertEqual(r.status_code, 200)
        self.assertEqual((await self.client.get('/api/model-preferences?model=fixture')).json()['options']['temperature'], 0.3)
        r = await self.client.post('/api/conversation-snapshots', json={'model':'fixture', 'messages':[{'role':'user','content':'Saved prompt'},{'role':'assistant','content':'Saved reply'}]})
        self.assertEqual(r.status_code, 201, r.text)
        detail = (await self.client.get(f"/api/conversations/{r.json()['id']}")).json()
        self.assertEqual(len(detail['messages']), 2)

    async def test_failed_stream_is_explicit_and_job_is_released(self):
        async with httpx.AsyncClient(base_url='http://runtime', transport=httpx.MockTransport(lambda request: httpx.Response(200, text='{"message":{"content":"partial"},"done":false}\n'))) as client:
            app.state.provider = OllamaProvider(client)
            cid = await self.create()
            r = await self.client.post('/api/chat', json={'model':'fixture','content':'Hi','conversation_id':cid})
            self.assertIn('"type": "error"', r.text)
            self.assertNotIn('"type": "done"', r.text)
            detail = (await self.client.get(f'/api/conversations/{cid}')).json()
            self.assertEqual(detail['messages'][-1]['statistics']['status'], 'failed')
            self.assertFalse(active_jobs)

    async def test_localhost_browser_can_create_and_send_chat(self):
        headers = {'Origin': 'http://localhost:3000', 'Sec-Fetch-Site': 'same-origin'}
        created = await self.client.post('/api/conversations', json={'model':'fixture'}, headers=headers)
        self.assertEqual(created.status_code, 201, created.text)
        response = await self.client.post('/api/chat', json={'model':'fixture', 'content':'Hi', 'conversation_id':created.json()['id']}, headers=headers)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertIn('"type": "done"', response.text)
        for origin in ['http://localhost:3001', 'http://localhost.evil.invalid:3000', 'https://localhost:3000', 'http://192.168.1.20:3000']:
            rejected = await self.client.post('/api/conversations', json={'model':'fixture'}, headers={'Origin':origin})
            self.assertEqual(rejected.status_code, 403, origin)

    async def test_provider_rejection_surfaces_actionable_error(self):
        async with httpx.AsyncClient(base_url='http://runtime', transport=httpx.MockTransport(lambda request: httpx.Response(404, json={'error':'model fixture not found'}))) as client:
            app.state.provider = OllamaProvider(client)
            response = await self.client.post('/api/chat', json={'model':'fixture','content':'Hello'})
            self.assertIn('model fixture not found', response.text)
            self.assertIn('"type": "error"', response.text)
            self.assertFalse(active_jobs)

    async def test_monitoring_persists_chat_and_playground_statistics_and_filters(self):
        from datetime import datetime, timezone
        from types import SimpleNamespace
        from backend.services.monitoring import save_sample
        app.state.metrics = SimpleNamespace(latest={'sampled_at':datetime.now(timezone.utc).isoformat(), 'cpu_percent':10}, error=None)
        try:
            await self.client.post('/api/chat', json={'model':'model-a', 'content':'private playground prompt'})
            cid = await self.create()
            await self.client.post('/api/chat', json={'model':'fixture', 'conversation_id':cid, 'content':'saved prompt'})
            for i in range(605):
                save_sample({'sampled_at':datetime.now(timezone.utc).isoformat(), 'cpu_percent':i/10})
            response = await self.client.get('/api/monitoring?model=model-a')
            self.assertEqual(response.status_code,200,response.text)
            data = response.json()
            self.assertEqual(len(data['runs']),1)
            self.assertEqual(data['runs'][0]['source'],'playground')
            self.assertEqual(data['runs'][0]['tokens_per_second'],2)
            self.assertNotIn('private playground prompt',response.text)
            self.assertEqual(len(data['system_history']),600)
            self.assertEqual(data['system_history'][0]['cpu_percent'],0)
            self.assertEqual(data['system_history'][-1]['cpu_percent'],60.4)
            self.assertEqual((await self.client.get('/api/monitoring?minutes=0')).status_code,422)
            first = (await self.client.get('/api/monitoring')).json()['runs'][0]['id']
            older = (await self.client.get(f'/api/monitoring?before_id={first}')).json()
            self.assertTrue(all(r['id']<first for r in older['runs']))
        finally:
            del app.state.metrics
