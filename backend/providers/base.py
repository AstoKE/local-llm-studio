from abc import ABC, abstractmethod
from typing import Any

class ProviderUnavailable(Exception):
    pass

class InferenceProvider(ABC):
    @abstractmethod
    async def status(self) -> dict[str, Any]: ...
    @abstractmethod
    async def models(self) -> list[dict[str, Any]]: ...
    @abstractmethod
    async def loaded(self) -> list[dict[str, Any]]: ...
