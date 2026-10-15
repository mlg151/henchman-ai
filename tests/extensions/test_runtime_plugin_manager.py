"""Tests for the runtime CLI plugin manager."""

from __future__ import annotations

from pathlib import Path

from henchman.cli.plugins import PluginManager


def _write(path: Path, content: str) -> None:
    """Write a file, creating parent directories as needed."""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


class TestRuntimePluginManager:
    """Tests for the UI PluginManager."""

    def test_load_plugins_from_directory_registers_extensions(self, tmp_path: Path) -> None:
        """Plugin .py files should load into the manager."""

        _write(
            tmp_path / "demo.py",
            '''from henchman.cli.plugins import UIPlugin

class DemoPlugin(UIPlugin):
    @property
    def name(self) -> str:
        return "demo"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def description(self) -> str:
        return "Demo plugin"

    def register(self, repl: object) -> None:
        pass
''',
        )

        manager = PluginManager(None)
        manager.load_plugins_from_directory(tmp_path)

        assert "demo" in manager.plugins

    def test_unregister_plugin_removes_registered_extension(self, tmp_path: Path) -> None:
        """Plugins can be removed from the registry by removing from the plugins dict."""

        _write(
            tmp_path / "demo.py",
            '''from henchman.cli.plugins import UIPlugin

class DemoPlugin(UIPlugin):
    @property
    def name(self) -> str:
        return "demo"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def description(self) -> str:
        return "Demo plugin"

    def register(self, repl: object) -> None:
        pass
''',
        )

        manager = PluginManager(None)
        manager.load_plugins_from_directory(tmp_path)

        assert "demo" in manager.plugins
        del manager.plugins["demo"]
        assert "demo" not in manager.plugins

    def test_reload_plugins_from_directory_refreshes_discovery(self, tmp_path: Path) -> None:
        """Reloading a directory should pick up newly added plugins."""

        _write(
            tmp_path / "demo.py",
            '''from henchman.cli.plugins import UIPlugin

class DemoPlugin(UIPlugin):
    @property
    def name(self) -> str:
        return "demo"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def description(self) -> str:
        return "Demo plugin"

    def register(self, repl: object) -> None:
        pass
''',
        )

        manager = PluginManager(None)
        manager.load_plugins_from_directory(tmp_path)

        # Add another plugin
        _write(
            tmp_path / "extra.py",
            '''from henchman.cli.plugins import UIPlugin

class ExtraPlugin(UIPlugin):
    @property
    def name(self) -> str:
        return "extra"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def description(self) -> str:
        return "Extra plugin"

    def register(self, repl: object) -> None:
        pass
''',
        )

        # Reload by calling load again — PluginManager doesn't clear existing plugins
        manager.load_plugins_from_directory(tmp_path)

        assert "demo" in manager.plugins
        assert "extra" in manager.plugins
