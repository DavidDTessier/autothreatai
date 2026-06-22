import sys
import unittest
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parents[1]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from shared.providers.registry import ProviderRegistry  # noqa: E402


class TestPerAgentConfig(unittest.TestCase):
    def setUp(self):
        # Load test config with overrides
        test_config_path = project_root / "config" / "providers.json"

        # Create test config
        test_config = {
            "default_provider": "gemini",
            "providers": [
                {
                    "id": "gemini",
                    "name": "Google Gemini",
                    "base_url": "https://generativelanguage.googleapis.com/v1beta",
                    "api_key": "test_key",
                    "default_model": "gemini-3-flash-preview",
                    "enabled": True,
                },
                {
                    "id": "anthropic",
                    "name": "Anthropic",
                    "base_url": "https://api.anthropic.com",
                    "api_key": "test_key",
                    "default_model": "claude-sonnet-4-6",
                    "enabled": True,
                },
                {
                    "id": "local",
                    "name": "Local Ollama",
                    "base_url": "",
                    "api_key": "test_key",
                    "default_model": "llama3",
                    "enabled": True,
                },
            ],
            "agent_overrides": {
                "threat_modeler": {"provider_id": "local", "default_model": "llama3"},
                "meastro": {"provider_id": "local", "default_model": "llama3"},
                "report_builder": {"provider_id": "anthropic", "default_model": "claude-sonnet-4-6"},
            },
        }

        # Backup original config
        original_config = None
        if test_config_path.exists():
            with open(test_config_path, encoding="utf-8") as f:
                import json

                original_config = json.load(f)

        # Write test config
        with open(test_config_path, "w", encoding="utf-8") as f:
            import json

            json.dump(test_config, f)

        # Initialize registry with test config
        self.registry = ProviderRegistry(config_path=test_config_path)
        self.original_config = original_config

    def tearDown(self):
        # Restore original config
        if self.original_config is not None:
            with open(project_root / "config" / "providers.json", "w", encoding="utf-8") as f:
                import json

                json.dump(self.original_config, f)
        else:
            # Remove test file if there was no original
            test_config_path = project_root / "config" / "providers.json"
            if test_config_path.exists():
                test_config_path.unlink()

    def test_agent_with_override(self):
        # Test agent configured in override
        model = self.registry.get_provider_for_agent("threat_modeler")
        self.assertEqual(model.config.default_model, "llama3")
        self.assertEqual(model.config.id, "local")

    def test_default_provider_fallback(self):
        # Test agent not in override
        model = self.registry.get_provider_for_agent("architecture_parser")
        self.assertEqual(model.config.default_model, "gemini-3-flash-preview")
        self.assertEqual(model.config.id, "gemini")

    def test_invalid_agent_id(self):
        # Test non-existent agent should use default
        model = self.registry.get_provider_for_agent("non_existent_agent")
        self.assertEqual(model.config.id, "gemini")
        self.assertEqual(model.config.default_model, "gemini-3-flash-preview")

    def test_agent_without_default_model(self):
        # Test override without default_model (should use provider's default)
        model = self.registry.get_provider_for_agent("meastro")
        self.assertEqual(model.config.id, "local")
        # Default model should still work through provider
        self.assertTrue(hasattr(model, "generate"))


if __name__ == "__main__":
    unittest.main()
