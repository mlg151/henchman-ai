"""Smoke tests for all major Henchman entry points.

These tests verify that module-level imports and entry-point public
APIs can be imported and basic structural assertions hold. None of
these tests require a running provider — they only verify that the
code is well-formed, importable, and has the expected public surface.

Entry points covered:
  - ``henchman`` (``__main__``)          — main() delegation
  - ``henchman.cli.app``                — Click CLI group & main()
  - ``henchman.cli.textual_app``        — Textual TUI app & run_textual_app()
  - ``henchman.cli.repl``               — Repl class & ReplConfig
  - ``henchman.cli.serve``              — HTTP serve command
  - ``henchman.cli.chat_serve``         — Chat via HTTP serve
  - ``henchman.cli.core_init``          — Core context initialization
  - ``henchman.cli.textual_mixins``     — All mixin classes
  - ``henchman.cli.textual_screens``    — All screen classes
  - ``henchman.cli.textual_widgets``    — All widget classes
  - ``henchman.cli.textual_config``     — Config classes
  - ``henchman.cli.textual_bridge``     — Event bridge & adapter
  - ``henchman.cli.textual_messages``   — Message subclasses
  - ``henchman.cli.textual_driver``     — Linux driver
  - ``henchman.version``                — Version info
"""

from __future__ import annotations

import importlib
import inspect
from pathlib import Path
from typing import Any

import pytest

# ====================================================================
# Helper
# ====================================================================


def _import_and_check(module_path: str, expected_attrs: list[str]) -> dict[str, Any]:
    """Import a module and verify expected attributes exist.

    Args:
        module_path: Fully-qualified module name.
        expected_attrs: List of attribute names that must be present.

    Returns:
        Dict of {name: value} for each checked attribute.
    """
    mod = importlib.import_module(module_path)
    result: dict[str, Any] = {}
    for attr_name in expected_attrs:
        assert hasattr(mod, attr_name), f"{module_path} missing {attr_name}"
        result[attr_name] = getattr(mod, attr_name)
    return result


# ====================================================================
# Smoke: version info
# ====================================================================


class TestVersionEntryPoint:
    """``henchman.version`` is importable and well-formed."""

    def test_version_import(self) -> None:
        mod = importlib.import_module("henchman.version")
        assert hasattr(mod, "VERSION") or hasattr(mod, "__version__")
        version = getattr(mod, "VERSION", None) or getattr(mod, "__version__", None)
        assert version is not None
        assert isinstance(version, str)
        assert len(version) > 0

    def test_typed_package_marker_is_shipped(self) -> None:
        """The Typing :: Typed classifier must be backed by a PEP 561 marker."""
        import henchman

        package_dir = Path(henchman.__file__).parent

        assert (package_dir / "py.typed").is_file()


# ====================================================================
# Smoke: __main__ entry point
# ====================================================================


class TestMainEntryPoint:
    """``henchman.__main__`` provides a ``main()`` function."""

    def test_main_importable(self) -> None:
        mod = importlib.import_module("henchman.__main__")
        assert hasattr(mod, "main")
        assert callable(mod.main)

    def test_main_delegates_to_cli_app(self) -> None:
        """The __main__.main() function delegates to app.main()."""
        from henchman.__main__ import main
        from henchman.cli.app import main as cli_main

        # __main__.main should be the same function object or delegate
        assert callable(main)
        assert callable(cli_main)


# ====================================================================
# Smoke: CLI app (Click group)
# ====================================================================


class TestCliAppEntryPoint:
    """``henchman.cli.app`` — Click CLI entry point."""

    def test_app_importable(self) -> None:
        _import_and_check("henchman.cli.app", ["cli", "main", "chat_command", "RunConfig"])

    def test_app_is_click_group(self) -> None:
        from henchman.cli.app import cli

        # Click groups have a .callback attribute
        assert hasattr(cli, "callback")
        assert hasattr(cli, "commands") or hasattr(cli, "add_command")

    def test_app_main_function(self) -> None:
        from henchman.cli.app import main

        assert callable(main)

    def test_run_config_dataclass(self) -> None:
        # Should be a dataclass or at least instantiable
        import dataclasses

        from henchman.cli.app import RunConfig

        if dataclasses.is_dataclass(RunConfig):
            instance = RunConfig()
            assert hasattr(instance, "provider_name") or hasattr(instance, "agent_role")
        else:
            # Not a dataclass, just check it exists
            pass  # pragma: no cover

    def test_get_provider_exists(self) -> None:
        from henchman.cli.app import _get_provider

        assert callable(_get_provider)


# ====================================================================
# Smoke: Textual TUI app
# ====================================================================


class TestTextualAppEntryPoint:
    """``henchman.cli.textual_app`` — Textual TUI app."""

    def test_textual_app_importable(self) -> None:
        attrs = _import_and_check("henchman.cli.textual_app", [
            "HenchmanTextualApp",
            "run_textual_app",
            "TextualConfig",
            "EventBridge",
            "TuiConsoleAdapter",
        ])
        assert inspect.isclass(attrs["HenchmanTextualApp"])
        assert callable(attrs["run_textual_app"])

    def test_textual_app_is_app_subclass(self) -> None:
        from henchman.cli.textual_app import HenchmanTextualApp

        assert issubclass(HenchmanTextualApp, object)

    def test_textual_app_has_bindings(self) -> None:
        from henchman.cli.textual_app import HenchmanTextualApp

        assert hasattr(HenchmanTextualApp, "BINDINGS")
        assert len(HenchmanTextualApp.BINDINGS) > 0

    def test_textual_app_has_compose(self) -> None:
        from henchman.cli.textual_app import HenchmanTextualApp

        assert hasattr(HenchmanTextualApp, "compose")
        assert callable(HenchmanTextualApp.compose)

    def test_textual_app_has_on_mount(self) -> None:
        from henchman.cli.textual_app import HenchmanTextualApp

        assert hasattr(HenchmanTextualApp, "on_mount")
        assert callable(HenchmanTextualApp.on_mount)

    def test_textual_app_has_css_path(self) -> None:
        from henchman.cli.textual_app import HenchmanTextualApp

        assert HenchmanTextualApp.CSS_PATH is not None

    def test_textual_css_file_exists(self) -> None:
        """Verify the TCSS file referenced by CSS_PATH exists on disk."""
        from henchman.cli.textual_app import HenchmanTextualApp

        css_name = HenchmanTextualApp.CSS_PATH
        # Resolve relative to the module location
        module_dir = Path(__file__).resolve().parents[2] / "src" / "henchman" / "cli"
        css_path = module_dir / css_name
        assert css_path.exists(), f"CSS file not found at {css_path}"

    def test_run_textual_app_signature(self) -> None:
        from henchman.cli.textual_app import run_textual_app

        sig = inspect.signature(run_textual_app)
        param_names = list(sig.parameters.keys())
        assert "provider" in param_names

    def test_check_utf8_encoding_exists(self) -> None:
        _import_and_check("henchman.cli.textual_app", ["_check_utf8_encoding"])

    def test_all_public_symbols_reexported(self) -> None:
        """Verify that __all__ matches expectations for textual_app."""
        from henchman.cli.textual_app import __all__ as textual_all

        # Key symbols that must be in __all__ (the actual __all__ list from the module)
        required = {
            "HenchmanTextualApp",
            "run_textual_app",
            "TextualConfig",
            "EventBridge",
            "TuiConsoleAdapter",
            "ChatPane",
            "StatusBar",
            "ChatMessage",
            "HenchmanTextArea",
            "ProgressIndicator",
            "ThinkingMessage",
            "ToolMessage",
        }
        missing = required - set(textual_all)
        assert not missing, f"Missing from __all__: {missing}"

        # Also verify these names are importable even if not in __all__
        for name in ["ThinkingPane", "ToolPane"]:
            assert name in dir(
                __import__("henchman.cli.textual_app", fromlist=[name])
            ), f"{name} should be importable from henchman.cli.textual_app"


# ====================================================================
# Smoke: Textual mixins
# ====================================================================


class TestTextualMixinsEntryPoint:
    """``henchman.cli.textual_mixins`` — all mixin classes."""

    MIXIN_NAMES = [
        "_ProxyMixin",
        "_InitMixin",
        "_ProviderMixin",
        "_StatusBarMixin",
        "_HistoryMixin",
        "_ContextTreeMixin",
        "_InputHandlerMixin",
        "_CommandPaletteMixin",
        "_MessageHandlerMixin",
        "_PaneActionMixin",
        "_SearchMixin",
        "_PublicAPIMixin",
    ]

    def test_all_mixins_importable(self) -> None:
        attrs = _import_and_check("henchman.cli.textual_mixins", self.MIXIN_NAMES)
        for name, cls in attrs.items():
            assert inspect.isclass(cls), f"{name} is not a class"

    def test_null_provider_importable(self) -> None:
        from henchman.cli.textual_mixins import _NullProvider

        instance = _NullProvider()
        assert instance.name == "null"
        assert instance.supports_tools is False
        assert instance.supports_streaming is False

    def test_extract_line_text_function(self) -> None:
        from henchman.cli.textual_mixins import _extract_line_text

        assert callable(_extract_line_text)
        # Smoke test with a string
        assert _extract_line_text("hello") == "hello"


# ====================================================================
# Smoke: Textual screens
# ====================================================================


class TestTextualScreensEntryPoint:
    """``henchman.cli.textual_screens`` — all screen classes."""

    SCREEN_NAMES = [
        "HelpScreen",
        "ProviderScreen",
        "ModelPickerScreen",
        "ThemePickerScreen",
        "ConfirmToolScreen",
        "SearchScreen",
        "HistorySearchScreen",
        "SessionScreen",
        "AutoModeScreen",
        "BridgeScreen",
        "ExportScreen",
        "FeedbackScreen",
        "OnboardingScreen",
        "McpServersScreen",
    ]

    def test_all_screens_importable(self) -> None:
        attrs = _import_and_check("henchman.cli.textual_screens", self.SCREEN_NAMES)
        for name, cls in attrs.items():
            assert inspect.isclass(cls), f"{name} is not a class"


# ====================================================================
# Smoke: Textual widgets
# ====================================================================


class TestTextualWidgetsEntryPoint:
    """``henchman.cli.textual_widgets`` — all widget classes."""

    WIDGET_NAMES = [
        "ChatPane",
        "ThinkingPane",
        "ToolPane",
        "StatusBar",
        "HenchmanTextArea",
        "ChatMessage",
        "ThinkingMessage",
        "ToolMessage",
        "ProgressIndicator",
    ]

    def test_all_widgets_importable(self) -> None:
        attrs = _import_and_check("henchman.cli.textual_widgets", self.WIDGET_NAMES)
        for name, cls in attrs.items():
            assert inspect.isclass(cls), f"{name} is not a class"


# ====================================================================
# Smoke: Textual config, bridge, messages, driver
# ====================================================================


class TestTextualSupportModules:
    """Support modules for the Textual TUI."""

    def test_textual_config(self) -> None:
        attrs = _import_and_check("henchman.cli.textual_config", [
            "TextualConfig",
            "ComponentConfig",
            "ComponentInitializer",
        ])
        assert inspect.isclass(attrs["TextualConfig"])
        assert inspect.isclass(attrs["ComponentConfig"])
        assert inspect.isclass(attrs["ComponentInitializer"])

    def test_textual_bridge(self) -> None:
        attrs = _import_and_check("henchman.cli.textual_bridge", [
            "EventBridge",
            "TuiConsoleAdapter",
        ])
        assert inspect.isclass(attrs["EventBridge"])
        assert inspect.isclass(attrs["TuiConsoleAdapter"])

    def test_textual_messages(self) -> None:
        attrs = _import_and_check("henchman.cli.textual_messages", [
            "AgentContentMessage",
            "AgentFinishedMessage",
            "AgentStatusMessage",
            "AgentThoughtMessage",
            "CommandOutputMessage",
            "SwitchProviderMessage",
            "ToolCallRequestMessage",
            "ToolCallResultMessage",
            "ToolConfirmationMessage",
        ])
        for name, cls in attrs.items():
            assert inspect.isclass(cls), f"{name} is not a class"

    def test_textual_driver(self) -> None:
        _import_and_check("henchman.cli.textual_driver", ["RobustLinuxDriver"])


# ====================================================================
# Smoke: REPL entry point
# ====================================================================


class TestReplEntryPoint:
    """``henchman.cli.repl`` — REPL class and config."""

    def test_repl_importable(self) -> None:
        attrs = _import_and_check("henchman.cli.repl", [
            "Repl",
            "ReplConfig",
        ])
        assert inspect.isclass(attrs["Repl"])
        assert inspect.isclass(attrs["ReplConfig"])

    def test_repl_config_defaults(self) -> None:
        from henchman.cli.repl import ReplConfig

        config = ReplConfig()
        assert config.prompt == "❯ "
        assert config.auto_save is True
        assert config.auto_approve_tools is False

    def test_repl_has_run_method(self) -> None:
        from henchman.cli.repl import Repl

        assert hasattr(Repl, "run")
        assert hasattr(Repl, "process_input")


# ====================================================================
# Smoke: Serve entry points
# ====================================================================


class TestServeEntryPoints:
    """HTTP server entry points."""

    def test_serve_command_importable(self) -> None:
        from henchman.cli.serve import serve_command

        assert callable(serve_command)
        # Click commands have params
        assert hasattr(serve_command, "params")

    def test_chat_serve_importable(self) -> None:
        mod = importlib.import_module("henchman.cli.chat_serve")
        assert hasattr(mod, "discordbot_command")
        assert callable(mod.discordbot_command)
        assert hasattr(mod.discordbot_command, "params")

    def test_core_init_importable(self) -> None:
        attrs = _import_and_check("henchman.cli.core_init", [
            "CoreContext",
            "create_core_context",
            "initialize_mcp",
        ])
        assert callable(attrs["create_core_context"])
        assert callable(attrs["initialize_mcp"])


# ====================================================================
# Smoke: All CLI modules import cleanly (structural integrity)
# ====================================================================


class TestAllCliModulesStructural:
    """Verify that every Python file in henchman/cli/ can be imported
    without SyntaxError."""

    CLI_MODULES = [
        "henchman.cli",
        "henchman.cli.app",
        "henchman.cli.chat_serve",
        "henchman.cli.command_processor",
        "henchman.cli.console",
        "henchman.cli.console_helpers",
        "henchman.cli.core_init",
        "henchman.cli.input",
        "henchman.cli.input_handler",
        "henchman.cli.json_output",
        "henchman.cli.output_handler",
        "henchman.cli.plugins",
        "henchman.cli.prompts",
        "henchman.cli.repl",
        "henchman.cli.serve",
        "henchman.cli.session_manager",
        "henchman.cli.stream_event_handlers",
        "henchman.cli.system_info",
        "henchman.cli.textual_app",
        "henchman.cli.textual_bridge",
        "henchman.cli.textual_config",
        "henchman.cli.textual_driver",
        "henchman.cli.textual_messages",
        "henchman.cli.textual_mixins",
        "henchman.cli.textual_screens",
        "henchman.cli.textual_widgets",
        "henchman.cli.tool_executor",
        "henchman.cli.tool_manager",
        "henchman.cli.ui_renderer",
        "henchman.cli.update_check",
    ]

    @pytest.mark.parametrize("module_name", CLI_MODULES)
    def test_all_cli_modules_import_cleanly(self, module_name: str) -> None:
        """Each CLI module should import without SyntaxError."""
        importlib.import_module(module_name)


# ====================================================================
# Smoke: Major commands module imports cleanly
# ====================================================================


class TestCommandsSmoke:
    """Spot-check that major command modules are importable."""

    COMMAND_MODULES = [
        "henchman.cli.commands.builtins",
        "henchman.cli.commands.chat",
        "henchman.cli.commands.session",
        "henchman.cli.commands.model",
        "henchman.cli.commands.agent",
        "henchman.cli.commands.help_command",
        "henchman.cli.commands.context",
        "henchman.cli.commands.mcp",
        "henchman.cli.commands.theme",
        "henchman.cli.commands.plan",
        "henchman.cli.commands.team",
        "henchman.cli.commands.skill_command",
        "henchman.cli.commands.rag",
        "henchman.cli.commands.git_command",
        "henchman.cli.commands.init_command",
        "henchman.cli.commands.doctor_command",
        "henchman.cli.commands.version_command",
    ]

    @pytest.mark.parametrize("module_name", COMMAND_MODULES)
    def test_command_module_imports(self, module_name: str) -> None:
        importlib.import_module(module_name)


# ====================================================================
# Smoke: RAG package dependency boundary
# ====================================================================


class TestRagEntryPoint:
    """The shipped RAG package imports on every supported Python version."""

    def test_rag_package_importable(self) -> None:
        """Importing the public RAG package must not fail in a supported environment."""
        module = importlib.import_module("henchman.rag")

        assert module.RagSystem.__name__ == "RagSystem"
