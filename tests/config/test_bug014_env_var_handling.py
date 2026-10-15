"""Tests for BUG-014: load_settings ignores HENCHMAN_PROVIDER/MODEL env vars.

The main load_settings() in config/__init__.py does not apply environment
variable overrides, so documented env vars like HENCHMAN_PROVIDER and
HENCHMAN_MODEL are silently ignored at runtime.
"""

from __future__ import annotations

import os

from henchman.config import load_settings


class TestBug014EnvVarHandling:
    """load_settings() should respect HENCHMAN_PROVIDER and HENCHMAN_MODEL."""

    def test_env_var_henchman_provider_is_respected(self) -> None:
        """HENCHMAN_PROVIDER should override the default provider."""
        os.environ["HENCHMAN_PROVIDER"] = "openai"
        try:
            settings = load_settings()
            assert settings.providers.default == "openai"
        finally:
            del os.environ["HENCHMAN_PROVIDER"]

    def test_env_var_henchman_model_is_respected(self) -> None:
        """HENCHMAN_MODEL should override the default provider's model."""
        os.environ["HENCHMAN_MODEL"] = "gpt-4o"
        try:
            settings = load_settings()
            # The default provider is "deepseek", so HENCHMAN_MODEL should
            # set deepseek's model to "gpt-4o"
            assert settings.providers.deepseek.get("model") == "gpt-4o"
        finally:
            del os.environ["HENCHMAN_MODEL"]

    def test_env_var_provider_and_model_together(self) -> None:
        """Both env vars should be applied together."""
        os.environ["HENCHMAN_PROVIDER"] = "anthropic"
        os.environ["HENCHMAN_MODEL"] = "claude-sonnet-4-20250514"
        try:
            settings = load_settings()
            assert settings.providers.default == "anthropic"
            assert settings.providers.anthropic.get("model") == "claude-sonnet-4-20250514"
        finally:
            del os.environ["HENCHMAN_PROVIDER"]
            del os.environ["HENCHMAN_MODEL"]
