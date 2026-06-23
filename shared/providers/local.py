import os

import httpx

from .base import ProviderConfig, ProviderInterface, ProviderModel


class LocalProvider(ProviderInterface):
    """Provider for local models via Ollama or LLMStudio-compatible APIs."""

    def __init__(self, config: ProviderConfig | None = None):
        # Determine base_url: environment variable > config > default
        base_url = os.getenv("OLLAMA_BASE_URL")
        if base_url is None and config is not None:
            base_url = config.base_url
        if base_url is None:
            base_url = "http://localhost:11434"

        # Create config with resolved base_url, preserving other settings
        if config is not None:
            self._config = ProviderConfig(
                id=config.id,
                name=config.name,
                base_url=base_url,
                api_key=config.api_key,
                default_model=config.default_model,
                enabled=config.enabled,
            )
        else:
            self._config = ProviderConfig(
                id="local",
                name="Local Model",
                base_url=base_url,
                enabled=True,
            )
        self._client = httpx.AsyncClient(timeout=30.0)

    @property
    def config(self) -> ProviderConfig:
        return self._config

    def get_models(self) -> list[ProviderModel]:
        """Fetch available models from Ollama API."""
        return []

    async def _fetch_models(self) -> list[ProviderModel]:
        """Async fetch for streaming context."""
        try:
            resp = await self._client.get(f"{self._config.base_url}/api/tags")
            if resp.status_code == 200:
                data = resp.json()
                models = []
                for m in data.get("models", []):
                    name = m.get("name")
                    if name:
                        models.append(ProviderModel(
                            id=f"local/{name}",
                            label=f"Local: {name}",
                            provider="local"
                        ))
                return models
        except Exception:
            pass
        return []

    async def generate(self, messages: list[dict], **options) -> str:
        """Generate text via Ollama API."""
        prompt = messages[-1].get("content", "")
        model = self._config.default_model or "llama3"

        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False,
        }

        resp = await self._client.post(
            f"{self._config.base_url}/api/generate",
            json=payload
        )
        resp.raise_for_status()
        return resp.json().get("response", "")
