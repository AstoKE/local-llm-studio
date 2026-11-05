from typing import Any
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
