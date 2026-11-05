import unittest
import httpx
from backend.providers.ollama import OllamaProvider
from backend.providers.base import ProviderUnavailable

class ProviderTests(unittest.IsolatedAsyncioTestCase):
    async def test_real_protocol_paths_and_metadata(self):
        def handle(request):
            responses = {'/api/version': {'version': 'test'}, '/api/tags': {'models': [{'name': 'fixture', 'size': 42}]}, '/api/ps': {'models': []}}
            return httpx.Response(200, json=responses[request.url.path])
        async with httpx.AsyncClient(base_url='http://runtime', transport=httpx.MockTransport(handle)) as client:
            provider = OllamaProvider(client)
            self.assertEqual(await provider.status(), {'version': 'test'})
            self.assertEqual(await provider.models(), [{'name': 'fixture', 'size': 42}])
            self.assertEqual(await provider.loaded(), [])

    async def test_unavailable_and_invalid_response(self):
        for response in [httpx.Response(500), httpx.Response(200, text='bad json'), httpx.Response(200, json=[])]:
            async with httpx.AsyncClient(base_url='http://runtime', transport=httpx.MockTransport(lambda request: response)) as client:
                with self.assertRaises(ProviderUnavailable):
                    await OllamaProvider(client).status()

    async def test_connection_failure(self):
        def handle(request):
            raise httpx.ConnectError('offline')
        async with httpx.AsyncClient(base_url='http://runtime', transport=httpx.MockTransport(handle)) as client:
            with self.assertRaises(ProviderUnavailable):
                await OllamaProvider(client).models()
