"""Tests for the root plugin command."""

from __future__ import annotations

from dataclasses import dataclass

from click.testing import CliRunner

from henchman.cli.commands.plugin_command import create_plugin_command
from henchman.extensions.plugin_manager import PluginManager


@dataclass
class _FakeEntryPoints:
    henchman_extensions: str | None = "demo.extension:DemoExtension"


@dataclass
class _FakeMetadata:
    name: str
    version: str
    description: str
    author: str
    entry_points: _FakeEntryPoints


@dataclass
class _FakeInstallation:
    metadata: _FakeMetadata
    installed_version: str
    installation_path: str
    enabled: bool = True


def test_plugin_list_renders_installed_plugins(monkeypatch) -> None:
    """`plugin list` should show installed plugins from the marketplace manager."""

    class FakePluginManager:
        def __init__(self) -> None:
            metadata = _FakeMetadata(
                name="demo-plugin",
                version="1.0.0",
                description="Demo plugin",
                author="Test Author",
                entry_points=_FakeEntryPoints(),
            )
            self.installed_plugins = {
                "demo-plugin": _FakeInstallation(
                    metadata=metadata,
                    installed_version="1.0.0",
                    installation_path="/tmp/demo-plugin",
                )
            }

        async def initialize(self) -> None:
            return None

        async def close(self) -> None:
            return None

    monkeypatch.setattr("henchman.cli.commands.plugin_command.PluginManager", FakePluginManager)

    runner = CliRunner()
    result = runner.invoke(create_plugin_command(), ["list"])

    assert result.exit_code == 0
    assert "demo-plugin" in result.output
    assert "1.0.0" in result.output


def test_plugin_remove_calls_manager(monkeypatch) -> None:
    """`plugin remove` should delegate to the marketplace manager."""

    removed: list[str] = []

    class FakePluginManager:
        def __init__(self) -> None:
            self.installed_plugins = {}

        async def initialize(self) -> None:
            return None

        async def close(self) -> None:
            return None

        async def uninstall_plugin(self, plugin_name: str) -> None:
            removed.append(plugin_name)

    monkeypatch.setattr("henchman.cli.commands.plugin_command.PluginManager", FakePluginManager)

    runner = CliRunner()
    result = runner.invoke(create_plugin_command(), ["remove", "demo-plugin"])

    assert result.exit_code == 0
    assert removed == ["demo-plugin"]


def test_plugin_install_surfaces_marketplace_unavailable_guidance(
    monkeypatch,
    tmp_path,
) -> None:
    """`plugin install` should fail cleanly when the bundled registry is unavailable."""

    class FakePluginManager(PluginManager):
        def __init__(self) -> None:
            super().__init__(data_dir=tmp_path)

    monkeypatch.setattr("henchman.cli.commands.plugin_command.PluginManager", FakePluginManager)

    runner = CliRunner()
    result = runner.invoke(create_plugin_command(), ["install", "demo-plugin"])

    assert result.exit_code == 1
    assert "error" in result.output.lower()


def test_plugin_install_surfaces_registry_miss_without_generic_marketplace_message(
    monkeypatch,
) -> None:
    """`plugin install` should keep configured-registry misses truthful."""

    class FakePluginManager:
        def __init__(self) -> None:
            self.installed_plugins = {}

        async def initialize(self) -> None:
            return None

        async def close(self) -> None:
            return None

        async def install_plugin(
            self,
            plugin_name: str,
            version: str | None = None,
            confirm_permissions: bool = True,
        ) -> None:
            del version, confirm_permissions
            raise ValueError(f"Plugin '{plugin_name}' not found in registry")

    monkeypatch.setattr("henchman.cli.commands.plugin_command.PluginManager", FakePluginManager)

    runner = CliRunner()
    result = runner.invoke(create_plugin_command(), ["install", "missing-plugin"])

    assert result.exit_code == 1
    assert "Plugin 'missing-plugin' not found in registry" in result.output


def test_plugin_install_surfaces_local_install_errors(monkeypatch) -> None:
    """`plugin install` should report local installation failures without crashing."""

    class FakePluginManager:
        def __init__(self) -> None:
            self.installed_plugins = {}

        async def initialize(self) -> None:
            return None

        async def close(self) -> None:
            return None

        async def install_plugin(
            self,
            plugin_name: str,
            version: str | None = None,
            confirm_permissions: bool = True,
        ) -> None:
            del plugin_name, version, confirm_permissions
            raise OSError("No space left on device")

    monkeypatch.setattr("henchman.cli.commands.plugin_command.PluginManager", FakePluginManager)

    runner = CliRunner()
    result = runner.invoke(create_plugin_command(), ["install", "demo-plugin"])

    assert result.exit_code == 1
    assert "No space left on device" in result.output


def test_plugin_help_mentions_local_scope_and_marketplace_limit() -> None:
    """The root command help should describe the truthful current scope."""

    runner = CliRunner()
    result = runner.invoke(create_plugin_command(), ["--help"])

    assert result.exit_code == 0
    normalized_output = " ".join(result.output.lower().split())
    assert "marketplace" in normalized_output
