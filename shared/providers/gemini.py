import httpx

from .base import ProviderConfig, ProviderInterface, ProviderModel


class GeminiProvider(ProviderInterface):
    """Provider for Google Gemini models."""

    DEFAULT_MODELS = [
        {"id": "gemini-3-flash-preview", "label": "Gemini 3 Flash Preview (Default)"},
        {"id": "gemini-3-pro-preview", "label": "Gemini 3 Pro Preview"},
        {"id": "gemini-2.5-pro", "label": "Gemini 2.5 Pro"},
        {"id": "gemini-flash-latest", "label": "Gemini 2.5 Flash Latest"},
        {"id": "gemini-2.0-flash", "label": "Gemini 2.0 Flash"},
    ]

    def __init__(self, config: ProviderConfig | None = None):
        self._config = config or ProviderConfig(
            id="gemini",
            name="Google Gemini",
            base_url="https://generativelanguage.googleapis.com/v1beta",
            api_key=None,
            default_model="gemini-3-flash-preview",
            enabled=True,
        )
        self._client = httpx.AsyncClient(timeout=60.0)

    @property
    def config(self) -> ProviderConfig:
        return self._config

    def get_models(self) -> list[ProviderModel]:
        return [
            ProviderModel(
                id=m["id"],
                label=m["label"],
                provider="google"
            )
            for m in self.DEFAULT_MODELS
        ]

    async def generate(self, messages: list[dict], **options) -> str:
        """Generate text via Gemini API."""
        if not self._config.api_key:
            raise ValueError("Gemini API key required")

        model = self._config.default_model or "gemini-3-flash-preview"

        # Convert messages to Gemini format
        contents = []
        for m in messages:
            if m["role"] == "user":
                contents.append({"role": "user", "parts": [{"text": m["content"]}]})
            elif m["role"] == "assistant":
                contents.append({"role": "model", "parts": [{"text": m["content"]}]})

        payload = {
            "contents": contents,
            "generationConfig": {
                "temperature": options.get("temperature", 0.7),
                "maxOutputTokens": options.get("max_tokens", 8192),
                "topP": options.get("top_p", 0.95),
            },
        }

        url = f"{self._config.base_url}/models/{model}:generateContent"
        if self._config.api_key:
            url += f"?key={self._config.api_key}"

        resp = await self._client.post(url, json=payload)
        resp.raise_for_status()
        data = resp.json()
        return data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
