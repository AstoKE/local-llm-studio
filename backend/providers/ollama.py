from typing import Any
from collections.abc import AsyncIterator
import httpx
from backend.providers.base import InferenceProvider, ProviderUnavailable

class OllamaProvider(InferenceProvider):
    def __init__(self, client: httpx.AsyncClient):
        self.client = client

    async def request(self, path: str) -> dict[str, Any]:
        try:
            response = await self.client.get(path)
            response.raise_for_status()
            data = response.json()
            if not isinstance(data, dict):
                raise ValueError('Invalid response')
            return data
        except (httpx.HTTPError, ValueError) as exc:
            raise ProviderUnavailable('Ollama is unavailable or returned an invalid response. Check the service and endpoint.') from exc

    async def status(self) -> dict[str, Any]:
        return await self.request('/api/version')

    async def models(self) -> list[dict[str, Any]]:
        return (await self.request('/api/tags')).get('models', [])

    async def loaded(self) -> list[dict[str, Any]]:
        return (await self.request('/api/ps')).get('models', [])

    async def stream(self, path: str, payload: dict[str, Any]) -> AsyncIterator[dict[str, Any]]:
        import json
        try:
            async with self.client.stream('POST', path, json=payload, timeout=httpx.Timeout(300, connect=5)) as response:
                if response.is_error:
                    await response.aread()
                    detail = ''
                    try:
                        detail = str(response.json().get('error', ''))[:500]
                    except (ValueError, AttributeError):
                        pass
                    raise ProviderUnavailable(f'Ollama rejected the request (HTTP {response.status_code}): {detail or "Check model availability and available memory."}')
                async for line in response.aiter_lines():
                    if not line:
                        continue
                    event = json.loads(line)
                    if not isinstance(event, dict):
                        raise ValueError('Invalid stream event')
                    if event.get('error'):
                        raise ProviderUnavailable(str(event['error'])[:500])
                    yield event
        except (httpx.HTTPError, ValueError) as exc:
            raise ProviderUnavailable('Ollama stream failed. Check the service, model and available memory.') from exc

    def chat(self, payload: dict[str, Any]) -> AsyncIterator[dict[str, Any]]:
        return self.stream('/api/chat', {**payload, 'stream': True, 'think': False})

    def pull(self, model: str) -> AsyncIterator[dict[str, Any]]:
        return self.stream('/api/pull', {'model': model, 'stream': True})

    async def operation(self, operation: str, model: str) -> dict[str, Any]:
        routes = {'show': ('POST', '/api/show', {'model': model}),
                  'delete': ('DELETE', '/api/delete', {'model': model}),
                  'load': ('POST', '/api/generate', {'model': model, 'stream': False, 'keep_alive': 300}),
                  'unload': ('POST', '/api/generate', {'model': model, 'stream': False, 'keep_alive': 0})}
        method, path, payload = routes[operation]
        try:
            response = await self.client.request(method, path, json=payload, timeout=300)
            response.raise_for_status()
            return response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise ProviderUnavailable('Ollama operation failed. Check model availability, runtime logs and memory.') from exc
