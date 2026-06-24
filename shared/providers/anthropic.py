import httpx

from .base import ProviderConfig, ProviderInterface, ProviderModel


class AnthropicProvider(ProviderInterface):
    """Provider for Anthropic Claude models."""

    DEFAULT_MODELS = [
        {"id": "claude-opus-4-7", "label": "Claude Opus 4.7"},
        {"id": "claude-sonnet-4-6", "label": "Claude Sonnet 4.6"},
        {"id": "claude-haiku-4-5", "label": "Claude Haiku 4.5"},
    ]

    def __init__(self, config: ProviderConfig | None = None):
        self._config = config or ProviderConfig(
            id="anthropic",
            name="Anthropic",
            base_url="https://api.anthropic.com",
            api_key=None,
            default_model="claude-sonnet-4-6",
            enabled=True,
        )
        self._client = httpx.AsyncClient(timeout=60.0)

    @property
    def config(self) -> ProviderConfig:
        return self._config

    def get_models(self) -> list[ProviderModel]:
        return [
            ProviderModel(id=f"anthropic/{m['id']}", label=f"Anthropic: {m['label']}", provider="anthropic")
            for m in self.DEFAULT_MODELS
        ]

    async def generate(self, messages: list[dict], **options) -> str:
        """Generate text via Anthropic API."""
        if not self._config.api_key:
            raise ValueError("Anthropic API key required")

        model = self._config.default_model or "claude-sonnet-4-6"
        model_id = model if model.startswith("anthropic/") else f"anthropic/{model}"

        payload = {
            "model": model_id.replace("anthropic/", ""),
            "messages": [
                {"role": m["role"], "content": m["content"]} for m in messages if m["role"] in ("user", "assistant")
            ],
            "max_tokens": options.get("max_tokens", 1024),
        }

        resp = await self._client.post(
            f"{self._config.base_url}/v1/messages",
            json=payload,
            headers={
                "x-api-key": self._config.api_key,
                "anthropic-version": "2023-06-01",
            },
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("content", [{}])[0].get("text", "")
