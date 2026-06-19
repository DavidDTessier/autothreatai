import httpx
from .base import ProviderInterface, ProviderModel, ProviderConfig


class LocalProvider(ProviderInterface):
    """Provider for local models via Ollama or LLMStudio-compatible APIs."""

    def __init__(self, config: ProviderConfig | None = None):
        self._config = config or ProviderConfig(
            id="local",
            name="Local Model",
            base_url="http://localhost:11434",
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