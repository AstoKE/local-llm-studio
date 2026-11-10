"""ASGI integration tests with isolated SQLite and deterministic provider fixtures."""
import os
import tempfile
import unittest
from unittest.mock import patch

_database = tempfile.TemporaryDirectory()
os.environ['STUDIO_DATABASE_URL'] = f'sqlite:///{_database.name}/test.db'
os.environ['STUDIO_LAN_MODE'] = 'false'
os.environ['STUDIO_ADMIN_PASSWORD_HASH'] = ''
os.environ['STUDIO_WEB_ORIGIN'] = 'http://127.0.0.1:3000'
os.environ['STUDIO_ADMIN_TOKEN'] = 'test-only-token-with-at-least-32-characters'

import httpx
from backend.main import app
from backend.database.session import Base, engine
from backend.models import entities
from backend.providers.ollama import OllamaProvider
from backend.services.chat import active_conversations, active_jobs
from backend.services.benchmarks import BenchmarkManager
from backend.services import runtime

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
        app.state.benchmarks = BenchmarkManager(app.state.provider)
        self.client = httpx.AsyncClient(base_url='http://127.0.0.1', transport=httpx.ASGITransport(app=app))

    async def asyncTearDown(self):
        await app.state.benchmarks.shutdown()
        runtime.benchmark_active = False
        runtime.model_operations.clear()
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

    async def test_benchmarks_are_sequential_and_block_other_inference(self):
        import asyncio
        from unittest.mock import patch
        gate = asyncio.Event()
        order = []
        async def chat(payload):
            await gate.wait()
            order.append(payload['options']['temperature'])
            yield {'message':{'content':'response'},'done':False}
            yield {'done':True,'eval_count':8,'eval_duration':2000000000}
        definition={'model':'fixture','prompt':'benchmark prompt','warmups':1,'repeats':1,'configurations':[
            {'name':'a','configuration':{'options':{'temperature':0.1}}},
            {'name':'b','configuration':{'options':{'temperature':0.2}}}]}
        with patch.object(app.state.provider,'chat',side_effect=chat):
            response=await self.client.post('/api/benchmarks',json=definition)
            self.assertEqual(response.status_code,202,response.text)
            identifier=response.json()['id']
            self.assertEqual((await self.client.post('/api/benchmarks',json=definition)).status_code,409)
            self.assertEqual((await self.client.post('/api/chat',json={'model':'fixture','content':'blocked'})).status_code,409)
            self.assertEqual((await self.client.post('/api/models/load',json={'model':'fixture'},headers={'Authorization':f"Bearer {os.environ['STUDIO_ADMIN_TOKEN']}"})).status_code,409)
            gate.set()
            await app.state.benchmarks.task
        detail=(await self.client.get(f'/api/benchmarks/{identifier}')).json()
        self.assertEqual(detail['status'],'completed')
        self.assertEqual(detail['progress'],4)
        self.assertEqual(order,[0.1,0.1,0.2,0.2])
        self.assertEqual(sum(not r['warmup'] for r in detail['results']),2)
        self.assertFalse(runtime.benchmark_active)
        from sqlalchemy import select
        from backend.database.session import SessionLocal
        from backend.models.entities import InferenceRun
        with SessionLocal() as session:
            self.assertEqual(len(session.scalars(select(InferenceRun).where(InferenceRun.source=='benchmark')).all()),2)

    async def test_immediate_benchmark_cancellation_and_recovery_release_runtime(self):
        from backend.schemas.benchmark import BenchmarkInput
        body=BenchmarkInput(model='fixture',prompt='test',configurations=[{'name':'a','configuration':{}}])
        identifier=app.state.benchmarks.start(body)
        await app.state.benchmarks.cancel(identifier)
        self.assertFalse(runtime.benchmark_active)
        self.assertEqual((await self.client.get(f'/api/benchmarks/{identifier}')).json()['status'],'cancelled')
        from backend.database.session import SessionLocal
        from backend.models.entities import Record
        with SessionLocal.begin() as session:
            session.add(Record(kind='benchmark',name='orphan',payload={'status':'running'}))
        BenchmarkManager.recover()
        history=(await self.client.get('/api/benchmarks')).json()['items']
        self.assertEqual(history[0]['status'],'interrupted')

    async def test_admin_settings_persist_without_returning_secrets(self):
        headers={'Authorization':f"Bearer {os.environ['STUDIO_ADMIN_TOKEN']}"}
        self.assertEqual((await self.client.get('/api/admin/settings')).status_code,401)
        body={'ollama_url':'http://127.0.0.1:11434','default_model':'fixture','configuration':{'options':{'temperature':0.4}}}
        self.assertEqual((await self.client.put('/api/admin/settings',json=body,headers=headers)).status_code,200)
        prefs=(await self.client.get('/api/preferences')).json()
        self.assertEqual(prefs['default_model'],'fixture')
        self.assertEqual(prefs['configuration']['options']['temperature'],0.4)
        response=await self.client.get('/api/admin/settings',headers=headers)
        self.assertNotIn('admin_token',response.text)
        self.assertNotIn('admin_password_hash',response.text)
        self.assertEqual((await self.client.put('/api/admin/settings',json={**body,'ollama_url':'http://user:secret@localhost:11434'},headers=headers)).status_code,422)
        active_jobs.add('busy')
        self.assertEqual((await self.client.post('/api/admin/maintenance',json={'operation':'clear_metrics'},headers=headers)).status_code,409)
        active_jobs.clear()
        self.assertEqual((await self.client.post('/api/admin/maintenance',json={'operation':'clear_metrics'},headers=headers)).status_code,200)
        self.assertEqual((await self.client.put('/api/preferences',json={'theme':'light'})).status_code,200)

    async def test_secure_lan_login_logout_and_session_hash(self):
        from pydantic import HttpUrl
        from backend.core.config import settings
        from backend.services.auth import COOKIE, hash_password
        from backend.api.auth import failures
        from backend.database.session import SessionLocal
        from backend.models.entities import Record
        from sqlalchemy import select
        config=settings()
        old=(config.lan_mode,config.web_origin,config.admin_password_hash)
        config.lan_mode=True
        config.web_origin=HttpUrl('https://studio.home.arpa')
        config.admin_password_hash=hash_password('long-test-password')
        failures.clear()
        try:
            async with httpx.AsyncClient(base_url='https://studio.home.arpa',transport=httpx.ASGITransport(app=app)) as browser:
                self.assertEqual((await browser.get('/api/conversations')).status_code,401)
                self.assertEqual((await browser.post('/api/auth/login',json={'password':'long-test-password'},headers={'Origin':'https://evil.invalid'})).status_code,403)
                response=await browser.post('/api/auth/login',json={'password':'long-test-password'},headers={'Origin':'https://studio.home.arpa'})
                self.assertEqual(response.status_code,200,response.text)
                cookie=response.headers['set-cookie'].lower()
                self.assertIn('httponly',cookie)
                self.assertIn('secure',cookie)
                self.assertIn('samesite=strict',cookie)
                self.assertTrue((await browser.get('/api/auth/me')).json()['authenticated'])
                self.assertEqual((await browser.get('/api/admin/settings')).status_code,200)
                token=browser.cookies.get(COOKIE)
                original_hash=config.admin_password_hash
                config.admin_password_hash=hash_password('rotated-test-password')
                self.assertEqual((await browser.get('/api/admin/settings')).status_code,401)
                config.admin_password_hash=original_hash
                with SessionLocal() as session:
                    row=session.scalar(select(Record).where(Record.kind=='auth_session'))
                    self.assertNotEqual(row.name,token)
                    self.assertNotIn(token,str(row.payload))
                await browser.post('/api/auth/logout',headers={'Origin':'https://studio.home.arpa'})
                self.assertEqual((await browser.get('/api/conversations')).status_code,401)
                browser.cookies.set(COOKIE,token)
                self.assertEqual((await browser.get('/api/admin/settings')).status_code,401)
        finally:
            config.lan_mode,config.web_origin,config.admin_password_hash=old
            failures.clear()

    async def test_login_rate_limit_and_expired_sessions(self):
        from backend.core.config import settings
        from backend.services.auth import hash_password
        from backend.api.auth import failures
        from backend.database.session import SessionLocal
        from backend.models.entities import Record
        from sqlalchemy import select
        config=settings()
        old=config.admin_password_hash
        config.admin_password_hash=hash_password('long-test-password')
        failures.clear()
        try:
            for _ in range(5):
                self.assertEqual((await self.client.post('/api/auth/login',json={'password':'wrong'})).status_code,401)
            self.assertEqual((await self.client.post('/api/auth/login',json={'password':'wrong'})).status_code,429)
            failures.clear()
            self.assertEqual((await self.client.post('/api/auth/login',json={'password':'long-test-password'})).status_code,200)
            with SessionLocal.begin() as session:
                row=session.scalar(select(Record).where(Record.kind=='auth_session'))
                row.payload={**row.payload,'expires_at':0}
            self.assertFalse((await self.client.get('/api/auth/me')).json()['authenticated'])
            self.assertEqual((await self.client.get('/api/admin/settings')).status_code,401)
        finally:
            config.admin_password_hash=old
            failures.clear()

    async def test_running_benchmark_cancellation_closes_provider_and_releases_jobs(self):
        import asyncio
        from unittest.mock import patch
        from backend.schemas.benchmark import BenchmarkInput
        entered=asyncio.Event()
        closed=[]
        async def chat(payload):
            try:
                entered.set()
                await asyncio.Event().wait()
                yield {'done':True}
            finally:
                closed.append(True)
        with patch.object(app.state.provider,'chat',side_effect=chat):
            identifier=app.state.benchmarks.start(BenchmarkInput(model='fixture',prompt='test',configurations=[{'name':'a','configuration':{}}]))
            await entered.wait()
            await app.state.benchmarks.cancel(identifier)
        self.assertTrue(closed)
        self.assertFalse(active_jobs)
        self.assertFalse(runtime.benchmark_active)
        self.assertEqual((await self.client.get(f'/api/benchmarks/{identifier}')).json()['status'],'cancelled')

    async def test_failed_benchmark_preserves_error_without_keeping_runtime_locked(self):
        from unittest.mock import patch
        from backend.schemas.benchmark import BenchmarkInput
        from backend.providers.base import ProviderUnavailable
        async def chat(payload):
            raise ProviderUnavailable('fixture model missing')
            yield
        with patch.object(app.state.provider,'chat',side_effect=chat):
            identifier=app.state.benchmarks.start(BenchmarkInput(model='fixture',prompt='test',configurations=[{'name':'a','configuration':{}}]))
            await app.state.benchmarks.task
        response=(await self.client.get(f'/api/benchmarks/{identifier}')).json()
        self.assertEqual(response['status'],'failed')
        self.assertIn('fixture model missing',str(response['results']))
        self.assertFalse(runtime.benchmark_active)
        self.assertFalse(active_jobs)

    async def test_lan_startup_requires_https_and_password_hash(self):
        from backend.core.config import settings
        config=settings()
        old=config.lan_mode
        config.lan_mode=True
        try:
            with self.assertRaises(RuntimeError):
                async with app.router.lifespan_context(app):
                    self.fail('Unsafe LAN mode was allowed')
        finally:
            config.lan_mode=old

    async def test_untrusted_host_and_oversized_payload_are_rejected(self):
        from backend.core.config import settings
        self.assertEqual((await self.client.get('/api/conversations',headers={'Host':'evil.invalid'})).status_code,400)
        config=settings()
        old=config.max_request_bytes
        config.max_request_bytes=65536
        try:
            response=await self.client.post('/api/chat',content=b'x'*65537,headers={'content-type':'application/json'})
            self.assertEqual(response.status_code,413,response.text)
            async def chunks():
                yield b'x'*32768
                yield b'x'*32769
            response=await self.client.post('/api/chat',content=chunks(),headers={'content-type':'application/json'})
            self.assertEqual(response.status_code,413,response.text)
        finally:
            config.max_request_bytes=old

    async def test_disconnect_before_response_headers_releases_chat_and_model_locks(self):
        from fastapi import Request
        from starlette.requests import ClientDisconnect
        from backend.api.workspace import chat, model_operation
        from backend.schemas.inference import ChatInput, ModelInput
        scope={'type':'http','method':'POST','path':'/api/chat','headers':[],'app':app,'asgi':{'spec_version':'2.4'}}
        async def disconnected():
            return {'type':'http.disconnect'}
        async def fail_send(message):
            raise OSError('client disconnected before headers')
        cid=await self.create()
        response=await chat(ChatInput(model='fixture',content='Hi',conversation_id=cid),Request(scope))
        self.assertTrue(active_jobs)
        with self.assertRaises(ClientDisconnect):
            await response(scope,disconnected,fail_send)
        self.assertFalse(active_jobs)
        self.assertFalse(active_conversations)
        response=await model_operation('pull',ModelInput(model='fixture'),Request(scope))
        self.assertTrue(runtime.model_operations)
        with self.assertRaises(ClientDisconnect):
            await response(scope,disconnected,fail_send)
        self.assertFalse(runtime.model_operations)
