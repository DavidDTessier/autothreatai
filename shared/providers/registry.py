import json
import os
from pathlib import Path
from typing import Dict, List

from .base import ProviderInterface, ProviderConfig
from .gemini import GeminiProvider
from .anthropic import AnthropicProvider
from .local import LocalProvider

# Resolve config path relative to project root (where config/providers.json lives)
CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "providers.json"

class ProviderRegistry:
    """Singleton registry that loads provider configs and instantiates adapters.

    The registry reads ``config/providers.json`` on first use and caches the
    provider instances.  Call ``ProviderRegistry.instance()`` to get the global
    object.
    """

    _instance = None

    def __init__(self, config_path: Path | None = None):
        self.config_path = config_path or CONFIG_PATH
        self._providers: Dict[str, ProviderInterface] = {}
        self._configs: Dict[str, ProviderConfig] = {}
        self._load_config()
        self._agent_overrides: Dict[str, ProviderConfig] = {}
        self._load_agent_overrides()

    @classmethod
    def instance(cls) -> "ProviderRegistry":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _load_config(self) -> None:
        if not self.config_path.exists():
            raise FileNotFoundError(f"Provider config not found: {self.config_path}")
        with open(self.config_path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        for p in raw.get("providers", []):
            cfg = ProviderConfig(
                id=p.get("id", ""),
                name=p.get("name", ""),
                base_url=p.get("base_url"),
                api_key=p.get("api_key"),
                default_model=p.get("default_model"),
                enabled=p.get("enabled", True),
            )
            self._configs[cfg.id] = cfg
            # instantiate the concrete provider based on id
            if cfg.id == "gemini":
                self._providers[cfg.id] = GeminiProvider(cfg)
            elif cfg.id == "anthropic":
                self._providers[cfg.id] = AnthropicProvider(cfg)
            elif cfg.id == "local":
                self._providers[cfg.id] = LocalProvider(cfg)
            else:
                # unknown provider – ignore for now
                continue

    def _load_agent_overrides(self) -> None:
        """Load per‑agent overrides from the config file into ``self._agent_overrides``.
        Expected JSON shape:
        {
            "agent_overrides": {
                "agent_id": {"provider_id": "gemini", "default_model": "gemini-1.5-pro", "api_key": "...", "base_url": "...", "enabled": true},
                ...
            }
        }
        """
        if not self.config_path.exists():
            return
        with open(self.config_path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        overrides = raw.get("agent_overrides", {})
        for agent_id, ov in overrides.items():
            cfg = ProviderConfig(
                id=ov.get("provider_id", ""),
                name="",
                base_url=ov.get("base_url"),
                api_key=ov.get("api_key"),
                default_model=ov.get("default_model"),
                enabled=ov.get("enabled", True),
            )
            self._agent_overrides[agent_id] = cfg

    def get_config_for_agent(self, agent_id: str) -> ProviderConfig | None:
        """Return the provider config for a specific agent, falling back to None if no override."""
        ov_cfg = self._agent_overrides.get(agent_id)
        if ov_cfg and ov_cfg.id:
            return ov_cfg
        return None

    def get_provider_for_agent(self, agent_id: str) -> ProviderInterface | None:
        """Return the provider instance for a specific agent, falling back to the default provider."""
        # Initialize agent-specific provider cache if not present
        if not hasattr(self, "_agent_providers"):
            self._agent_providers: Dict[str, ProviderInterface] = {}

        # Check for per‑agent override first
        ov_cfg = self._agent_overrides.get(agent_id)
        if ov_cfg and ov_cfg.id:
            # Ensure agent-specific provider is instantiated
            if agent_id not in self._agent_providers:
                if ov_cfg.id == "gemini":
                    self._agent_providers[agent_id] = GeminiProvider(ov_cfg)
                elif ov_cfg.id == "anthropic":
                    self._agent_providers[agent_id] = AnthropicProvider(ov_cfg)
                elif ov_cfg.id == "local":
                    self._agent_providers[agent_id] = LocalProvider(ov_cfg)
                else:
                    return None
            return self._agent_providers.get(agent_id)
        
        # No override – use the globally configured default provider
        default_id = self.default_provider()
        return self._providers.get(default_id)

    def get_provider(self, provider_id: str) -> ProviderInterface | None:
        return self._providers.get(provider_id)

    def list_providers(self) -> List[ProviderConfig]:
        return list(self._configs.values())

    def default_provider(self) -> str:
        # fallback to first enabled provider if not set
        raw = json.load(open(self.config_path, "r", encoding="utf-8"))
        return raw.get("default_provider", self.list_providers()[0].id if self.list_providers() else "")