"""Tests for settings loading and file discovery."""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from henchman.config.schema import Settings
from henchman.config.settings import deep_merge, load_settings

if TYPE_CHECKING:
    from collections.abc import Iterator


class TestDeepMerge:
    """Tests for deep_merge utility function."""

    def test_empty_dicts(self) -> None:
        """Test merging empty dicts."""
        assert deep_merge({}, {}) == {}

    def test_base_only(self) -> None:
        """Test when override is empty."""
        base = {"a": 1, "b": 2}
        assert deep_merge(base, {}) == {"a": 1, "b": 2}

    def test_override_only(self) -> None:
        """Test when base is empty."""
        override = {"a": 1, "b": 2}
        assert deep_merge({}, override) == {"a": 1, "b": 2}

    def test_simple_override(self) -> None:
        """Test simple key override."""
        base = {"a": 1, "b": 2}
        override = {"b": 3, "c": 4}
        result = deep_merge(base, override)
        assert result == {"a": 1, "b": 3, "c": 4}

    def test_nested_merge(self) -> None:
        """Test nested dict merging."""
        base = {"a": {"x": 1, "y": 2}, "b": 3}
        override = {"a": {"y": 10, "z": 20}}
        result = deep_merge(base, override)
        assert result == {"a": {"x": 1, "y": 10, "z": 20}, "b": 3}

    def test_override_non_dict_with_dict(self) -> None:
        """Test overriding a non-dict value with dict."""
        base = {"a": 1}
        override = {"a": {"nested": True}}
        result = deep_merge(base, override)
        assert result == {"a": {"nested": True}}

    def test_override_dict_with_non_dict(self) -> None:
        """Test overriding a dict value with non-dict."""
        base = {"a": {"nested": True}}
        override = {"a": "string"}
        result = deep_merge(base, override)
        assert result == {"a": "string"}

    def test_does_not_mutate_inputs(self) -> None:
        """Test that original dicts are not mutated."""
        base = {"a": {"x": 1}}
        override = {"a": {"y": 2}}
        deep_merge(base, override)
        assert base == {"a": {"x": 1}}
        assert override == {"a": {"y": 2}}


class TestLoadSettings:
    """Tests for load_settings function."""

    @pytest.fixture
    def temp_home(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
        """Create a temporary home directory."""
        home = tmp_path / "home"
        home.mkdir()
        monkeypatch.setenv("HOME", str(home))
        return home

    @pytest.fixture
    def temp_cwd(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
        """Create and change to a temporary working directory."""
        cwd = tmp_path / "workspace"
        cwd.mkdir()
        monkeypatch.chdir(cwd)
        return cwd

    @pytest.fixture
    def clean_env(self, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
        """Remove HENCHMAN_ environment variables."""
        for key in list(os.environ.keys()):
            if key.startswith("HENCHMAN_"):
                monkeypatch.delenv(key, raising=False)
        yield

    def test_default_settings(
        self, temp_home: Path, temp_cwd: Path, clean_env: None
    ) -> None:
        """Test loading default settings when no files exist."""
        settings = load_settings()
        assert isinstance(settings, Settings)
        assert settings.providers.default == "deepseek"

    def test_user_settings(
        self, temp_home: Path, temp_cwd: Path, clean_env: None
    ) -> None:
        """Test loading user settings from ~/.henchman/settings.yaml."""
        henchman_dir = temp_home / ".henchman"
        henchman_dir.mkdir()
        (henchman_dir / "settings.yaml").write_text(
            """
providers:
  default: openai
  openai:
    model: gpt-4o
"""
        )
        settings = load_settings()
        assert settings.providers.default == "openai"
        assert settings.providers.openai == {"model": "gpt-4o"}

    def test_workspace_settings(
        self, temp_home: Path, temp_cwd: Path, clean_env: None
    ) -> None:
        """Test loading workspace settings from .henchman/settings.yaml."""
        henchman_dir = temp_cwd / ".henchman"
        henchman_dir.mkdir()
        (henchman_dir / "settings.yaml").write_text(
            """
tools:
  shell_timeout: 120
"""
        )
        settings = load_settings()
        assert settings.tools.shell_timeout == 120

    def test_workspace_overrides_user(
        self, temp_home: Path, temp_cwd: Path, clean_env: None
    ) -> None:
        """Test that workspace settings override user settings."""
        # User settings
        user_dir = temp_home / ".henchman"
        user_dir.mkdir()
        (user_dir / "settings.yaml").write_text(
            """
providers:
  default: openai
tools:
  shell_timeout: 60
"""
        )
        # Workspace settings
        workspace_dir = temp_cwd / ".henchman"
        workspace_dir.mkdir()
        (workspace_dir / "settings.yaml").write_text(
            """
providers:
  default: anthropic
"""
        )
        settings = load_settings()
        assert settings.providers.default == "anthropic"
        assert settings.tools.shell_timeout == 60  # From user

    def test_env_override_provider(
        self, temp_home: Path, temp_cwd: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test HENCHMAN_PROVIDER env var overrides settings."""
        monkeypatch.setenv("HENCHMAN_PROVIDER", "ollama")
        settings = load_settings()
        assert settings.providers.default == "ollama"

    def test_env_override_model(
        self, temp_home: Path, temp_cwd: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test HENCHMAN_MODEL env var overrides settings."""
        monkeypatch.setenv("HENCHMAN_MODEL", "gpt-4-turbo")
        settings = load_settings()
        # Model is stored in provider-specific settings
        provider = settings.providers.default
        assert settings.providers.model_dump()[provider].get("model") == "gpt-4-turbo"

    def test_json_settings_file(
        self, temp_home: Path, temp_cwd: Path, clean_env: None
    ) -> None:
        """Test loading settings from JSON file."""
        henchman_dir = temp_home / ".henchman"
        henchman_dir.mkdir()
        (henchman_dir / "settings.json").write_text(
            '{"providers": {"default": "anthropic"}}'
        )
        settings = load_settings()
        assert settings.providers.default == "anthropic"

    def test_yaml_preferred_over_json(
        self, temp_home: Path, temp_cwd: Path, clean_env: None
    ) -> None:
        """Test that YAML takes precedence over JSON."""
        henchman_dir = temp_home / ".henchman"
        henchman_dir.mkdir()
        (henchman_dir / "settings.yaml").write_text("providers:\n  default: openai")
        (henchman_dir / "settings.json").write_text('{"providers": {"default": "anthropic"}}')
        settings = load_settings()
        assert settings.providers.default == "openai"

    def test_invalid_yaml_raises_error(
        self, temp_home: Path, temp_cwd: Path, clean_env: None
    ) -> None:
        """Test that invalid YAML raises ConfigError."""
        from henchman.config.settings import ConfigError

        henchman_dir = temp_home / ".henchman"
        henchman_dir.mkdir()
        (henchman_dir / "settings.yaml").write_text("invalid: yaml: content:")
        with pytest.raises(ConfigError):
            load_settings()

    def test_invalid_settings_structure(
        self, temp_home: Path, temp_cwd: Path, clean_env: None
    ) -> None:
        """Test that invalid settings structure raises ConfigError."""
        from henchman.config.settings import ConfigError

        henchman_dir = temp_home / ".henchman"
        henchman_dir.mkdir()
        (henchman_dir / "settings.yaml").write_text(
            """
tools:
  sandbox: invalid_value
"""
        )
        with pytest.raises(ConfigError):
            load_settings()


class TestSettingsFileDiscovery:
    """Tests for settings file discovery logic."""

    @pytest.fixture
    def temp_home(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
        """Create a temporary home directory."""
        home = tmp_path / "home"
        home.mkdir()
        monkeypatch.setenv("HOME", str(home))
        return home

    @pytest.fixture
    def temp_cwd(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
        """Create and change to a temporary working directory."""
        cwd = tmp_path / "workspace"
        cwd.mkdir()
        monkeypatch.chdir(cwd)
        return cwd

    def test_no_config_directories(
        self, temp_home: Path, temp_cwd: Path
    ) -> None:
        """Test when no .henchman directories exist."""
        from henchman.config.settings import discover_settings_files

        files = discover_settings_files()
        assert files == []

    def test_user_config_only(
        self, temp_home: Path, temp_cwd: Path
    ) -> None:
        """Test discovering user config only."""
        from henchman.config.settings import discover_settings_files

        henchman_dir = temp_home / ".henchman"
        henchman_dir.mkdir()
        settings_file = henchman_dir / "settings.yaml"
        settings_file.write_text("providers:\n  default: openai")

        files = discover_settings_files()
        assert len(files) == 1
        assert files[0] == settings_file

    def test_workspace_config_only(
        self, temp_home: Path, temp_cwd: Path
    ) -> None:
        """Test discovering workspace config only."""
        from henchman.config.settings import discover_settings_files

        henchman_dir = temp_cwd / ".henchman"
        henchman_dir.mkdir()
        settings_file = henchman_dir / "settings.yaml"
        settings_file.write_text("tools:\n  shell_timeout: 120")

        files = discover_settings_files()
        assert len(files) == 1
        assert files[0] == settings_file

    def test_both_configs_ordered(
        self, temp_home: Path, temp_cwd: Path
    ) -> None:
        """Test that user config comes before workspace config."""
        from henchman.config.settings import discover_settings_files

        user_dir = temp_home / ".henchman"
        user_dir.mkdir()
        user_file = user_dir / "settings.yaml"
        user_file.write_text("providers:\n  default: openai")

        workspace_dir = temp_cwd / ".henchman"
        workspace_dir.mkdir()
        workspace_file = workspace_dir / "settings.yaml"
        workspace_file.write_text("tools:\n  shell_timeout: 120")

        files = discover_settings_files()
        assert len(files) == 2
        assert files[0] == user_file
        assert files[1] == workspace_file

    def test_yml_extension(
        self, temp_home: Path, temp_cwd: Path
    ) -> None:
        """Test discovering .yml extension files."""
        from henchman.config.settings import discover_settings_files

        henchman_dir = temp_home / ".henchman"
        henchman_dir.mkdir()
        settings_file = henchman_dir / "settings.yml"
        settings_file.write_text("providers:\n  default: openai")

        files = discover_settings_files()
        assert len(files) == 1
        assert files[0] == settings_file

    def test_empty_henchman_directory(
        self, temp_home: Path, temp_cwd: Path
    ) -> None:
        """Test when .henchman directory exists but has no settings files."""
        from henchman.config.settings import discover_settings_files

        # Create empty .henchman directories
        (temp_home / ".henchman").mkdir()
        (temp_cwd / ".henchman").mkdir()

        files = discover_settings_files()
        assert files == []

    def test_json_fallback(
        self, temp_home: Path, temp_cwd: Path
    ) -> None:
        """Test discovering JSON when no YAML files exist."""
        from henchman.config.settings import discover_settings_files

        henchman_dir = temp_home / ".henchman"
        henchman_dir.mkdir()
        settings_file = henchman_dir / "settings.json"
        settings_file.write_text('{"providers": {"default": "openai"}}')

        files = discover_settings_files()
        assert len(files) == 1
        assert files[0] == settings_file
