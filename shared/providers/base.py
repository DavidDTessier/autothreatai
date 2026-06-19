from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class ProviderModel:
    id: str
    label: str
    provider: str


@dataclass
class ProviderConfig:
    id: str
    name: str
    base_url: str | None = None
    api_key: str | None = None
    default_model: str | None = None
    enabled: bool = True


class ProviderInterface(ABC):
    @abstractmethod
    def get_models(self) -> list[ProviderModel]:
        """Return list of available models for this provider."""
        pass

    @abstractmethod
    async def generate(self, messages: list[dict[str, Any]], **options: Any) -> str:
        """Generate response for given messages. Returns the text response."""
        pass

    @property
    def config(self) -> ProviderConfig | None:
        return None