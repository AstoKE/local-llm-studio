from abc import ABC, abstractmethod
from typing import Any
from collections.abc import AsyncIterator

class ProviderUnavailable(Exception):
    pass

class InferenceProvider(ABC):
    @abstractmethod
    async def status(self) -> dict[str, Any]: ...
    @abstractmethod
    async def models(self) -> list[dict[str, Any]]: ...
    @abstractmethod
    async def loaded(self) -> list[dict[str, Any]]: ...

    @abstractmethod
    def chat(self, payload: dict[str, Any]) -> AsyncIterator[dict[str, Any]]: ...
    @abstractmethod
    def pull(self, model: str) -> AsyncIterator[dict[str, Any]]: ...
    @abstractmethod
    async def operation(self, operation: str, model: str) -> dict[str, Any]: ...
