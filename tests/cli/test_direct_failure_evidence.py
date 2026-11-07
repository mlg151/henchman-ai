"""Direct CLI failures project diagnostics without changing execution objects."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import click
import pytest
from rich.console import Console

from henchman.cli.app import _get_provider, _prepare_runtime_context
from henchman.cli.command_processor import CommandProcessor
from henchman.cli.commands import CommandContext
from henchman.cli.core_init import initialize_mcp
from henchman.cli.evidence import runtime_exception_text
from henchman.cli.output_handler import OutputHandler
from henchman.cli.plugins import PluginManager, UIPlugin
from henchman.cli.session_manager import ReplSessionManager
from henchman.cli.ui_renderer import UIRenderer
from henchman.config.schema import ProviderSettings, Settings
from henchman.core.session_manager import SessionManager
from henchman.utils.evidence_redaction import EvidenceRedactor


@pytest.fixture
def runtime(tmp_path: Path) -> SimpleNamespace:
    transcript = StringIO()
    renderer = UIRenderer(console=Console(file=transcript, width=1000, highlight=False))
    provider = SimpleNamespace(api_key="configured-[bold]-canary")
    settings = Settings(providers=ProviderSettings(deepseek={"api_key": "settings-canary"}))
    settings.ui.mcp_logging = True
    sessions = ReplSessionManager(
        SessionManager(data_dir=tmp_path / "sessions"), auto_save=False,
        settings=settings, provider=provider,
    )
    sessions.set_session(sessions.create_session("project"))
    sessions.session_manager.evidence_redactor.register_secret("chain-canary")
    output = OutputHandler(renderer, MagicMock(), sessions, provider)
    repl = SimpleNamespace(
        renderer=renderer, provider=provider, settings=settings,
        session_manager=sessions, orchestrator=None,
    )
    return SimpleNamespace(
        output=output, repl=repl, sessions=sessions, provider=provider,
        settings=settings, transcript=transcript,
    )


async def test_background_mcp_failure_masks_shared_policy_and_keeps_task_contract(
    runtime: SimpleNamespace, capsys: pytest.CaptureFixture[str],
) -> None:
    failure = RuntimeError("connect configured-[bold]-canary settings-canary")
    context = SimpleNamespace(
        session_manager=runtime.sessions, provider=runtime.provider,
        settings=runtime.settings, background_tasks=set(), tool_registry=MagicMock(),
        mcp_manager=SimpleNamespace(clients={}, connect_all=AsyncMock(side_effect=failure)),
    )
    initialize_mcp(context)
    await asyncio.gather(*context.background_tasks)
    shown = capsys.readouterr().out
    assert "canary" not in shown
    assert "Failed to connect to MCP servers" in shown
    assert "[REDACTED]" in shown
    assert str(failure) == "connect configured-[bold]-canary settings-canary"
    assert all(task.done() and task.exception() is None for task in context.background_tasks)
    context.tool_registry.register.assert_not_called()


def test_plugin_load_warning_masks_filename_and_exception_but_continues(
    runtime: SimpleNamespace, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    directory = tmp_path / "plugins"
    directory.mkdir()
    for name in ("configured-[bold]-canary.py", "ordinary.py"):
        (directory / name).write_text("")
    manager = PluginManager(runtime.repl)
    failure = RuntimeError("load configured-[bold]-canary settings-canary")
    loader = MagicMock(side_effect=failure)
    monkeypatch.setattr(manager, "_load_plugin_from_file", loader)
    manager.load_plugins_from_directory(directory)
    shown = runtime.transcript.getvalue()
    assert "canary" not in shown
    assert shown.count("Failed to load plugin") == 2
    assert loader.call_count == 2
    assert str(failure) == "load configured-[bold]-canary settings-canary"


def test_plugin_instantiation_warning_masks_class_name_and_exception(runtime: SimpleNamespace) -> None:
    failure = RuntimeError("instantiate configured-[bold]-canary")

    class BrokenPlugin(UIPlugin):
        def __init__(self) -> None:
            raise failure

        @property
        def name(self) -> str:
            return "broken"

        def register(self, repl: object) -> None:
            raise AssertionError("Must not register a failed instance")

    manager = PluginManager(runtime.repl)
    assert manager._try_register_plugin_class("configured-[bold]-canary", BrokenPlugin) is False
    shown = runtime.transcript.getvalue()
    assert "canary" not in shown
    assert "Failed to instantiate plugin" in shown
    assert not manager.plugins
    assert str(failure) == "instantiate configured-[bold]-canary"


async def test_command_failure_masks_messages_and_tracebacks_but_preserves_arguments(
    runtime: SimpleNamespace,
) -> None:
    processor = CommandProcessor(runtime.output, MagicMock(), runtime.sessions, runtime.provider)
    seen = []
    cause = ValueError("chain-canary")
    failure = RuntimeError("configured-[bold]-canary settings-canary")
    failure.add_note("Authorization: Bearer note-header-canary")

    async def execute(context: CommandContext) -> None:
        seen.append(context.args)
        raise failure from cause

    command = SimpleNamespace(name="failure", execute=execute)
    processor.command_registry.register(command)
    assert await processor.handle_command(
        "/failure configured-[bold]-canary", MagicMock(), runtime.repl,
    ) is True
    shown = runtime.transcript.getvalue()
    assert "canary" not in shown
    assert "RuntimeError" in shown and "ValueError" in shown
    assert "direct cause" in shown
    assert seen == [["configured-[bold]-canary"]]
    assert failure.__cause__ is cause
    assert failure.__notes__ == ["Authorization: Bearer note-header-canary"]


async def test_unknown_command_masks_credential_named_command(runtime: SimpleNamespace) -> None:
    processor = CommandProcessor(runtime.output, MagicMock(), runtime.sessions, runtime.provider)
    assert await processor.handle_command("/settings-canary", MagicMock(), runtime.repl) is True
    assert "settings-canary" not in runtime.transcript.getvalue()
    assert "Unknown command: /[REDACTED]" in runtime.transcript.getvalue()


def test_provider_setup_click_error_uses_supplied_settings_and_keeps_cause(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = Settings(providers=ProviderSettings(deepseek={"api_key": "factory-canary"}))
    failure = ValueError("invalid factory-canary")
    factory = MagicMock(side_effect=failure)
    monkeypatch.setattr("henchman.providers.factory.create_configured_provider", factory)
    with pytest.raises(click.ClickException) as raised:
        _get_provider(settings)
    assert str(raised.value) == "Unable to configure provider: invalid [REDACTED]"
    assert raised.value.__cause__ is failure
    assert str(failure) == "invalid factory-canary"
    factory.assert_called_once_with(settings.providers)


@pytest.mark.parametrize("entrypoint", [_get_provider, _prepare_runtime_context])
def test_failed_settings_load_masks_environment_credentials_and_keeps_cause(
    monkeypatch: pytest.MonkeyPatch, entrypoint: Callable[[], object],
) -> None:
    monkeypatch.setenv("HENCHMAN_FAILURE_TEST_TOKEN", "environment-canary")
    failure = ValueError("invalid environment-canary")
    loader_name = "load_settings_snapshot" if entrypoint is _prepare_runtime_context else "load_settings"
    monkeypatch.setattr(f"henchman.config.{loader_name}", MagicMock(side_effect=failure))
    with pytest.raises(click.ClickException) as raised:
        entrypoint()
    assert "environment-canary" not in str(raised.value)
    assert "Unable to configure provider" in str(raised.value)
    assert raised.value.__cause__ is failure


def test_exception_snapshot_masks_auth_headers_source_lines_and_notes() -> None:
    runtime = SimpleNamespace(_evidence_redactor=EvidenceRedactor())
    try:
        raise RuntimeError("Authorization: Bearer source-header-canary")
    except RuntimeError as failure:
        failure.add_note("Proxy-Authorization: Basic note-header-canary")
        before = (str(failure), failure.__traceback__, failure.__notes__.copy())
        shown = runtime_exception_text(runtime, failure, include_traceback=True)
        assert "source-header-canary" not in shown
        assert "note-header-canary" not in shown
        assert "RuntimeError" in shown and "test_exception_snapshot" in shown
        assert "[REDACTED]" in shown
        assert (str(failure), failure.__traceback__, failure.__notes__) == before


def test_exception_snapshot_projects_nested_chains_and_groups_without_mutation() -> None:
    runtime = SimpleNamespace(_evidence_redactor=EvidenceRedactor())
    cause = ValueError("Cookie: sid=cause-header-canary")
    child = RuntimeError("Set-Cookie: child-header-canary")
    child.__cause__ = cause
    nested = ValueError("Cookie: sid=nested-header-canary")
    group = ExceptionGroup("Diagnostic group", [child, ExceptionGroup("Nested", [nested])])
    group.add_note("Authorization: Bearer group-header-canary")
    shown = runtime_exception_text(runtime, group, include_traceback=True)
    for value in ("cause-header-canary", "child-header-canary", "group-header-canary", "nested-header-canary"):
        assert value not in shown
    assert "Diagnostic group" in shown and "Nested" in shown
    assert "direct cause" in shown and "[REDACTED]" in shown
    assert group.exceptions[0] is child
    assert child.__cause__ is cause
    assert str(child) == "Set-Cookie: child-header-canary"
    assert group.__notes__ == ["Authorization: Bearer group-header-canary"]
    assert runtime._evidence_redactor.text("Diagnostic group") == "Diagnostic group"


def test_successful_plugin_load_masks_notice_without_changing_registration(
    runtime: SimpleNamespace, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    import sys

    path = tmp_path / "configured-[bold]-canary.py"
    source = (
        "from henchman.cli.plugins import UIPlugin\n"
        "class OrdinaryPlugin(UIPlugin):\n"
        "    @property\n"
        "    def name(self): return 'ordinary'\n"
        "    def register(self, repl): repl.registered_plugin = self\n"
    )
    path.write_text(source)
    monkeypatch.setitem(sys.modules, f"henchman_plugin_{path.stem}", MagicMock())
    manager = PluginManager(runtime.repl)
    manager._load_plugin_from_file(path)
    shown = runtime.transcript.getvalue()
    assert "configured-" not in shown
    assert "canary" not in shown
    assert "Loaded plugins from [REDACTED].py" in shown
    assert manager.plugins["ordinary"] is runtime.repl.registered_plugin
    assert manager.plugins["ordinary"].__class__.__module__ == f"henchman_plugin_{path.stem}"
    assert path.read_text() == source


@pytest.mark.parametrize("message", [
    "invalid configured-[bold]-canary settings-canary",
    "Authorization: Bearer unrelated-resume-header-canary",
])
def test_resume_failure_masks_click_message_and_preserves_load_failure(
    runtime: SimpleNamespace, monkeypatch: pytest.MonkeyPatch, message: str,
) -> None:
    from henchman.cli.app import _setup_repl_session

    failure = ValueError(message)
    core = runtime.sessions.session_manager
    monkeypatch.setattr(core, "get_project_current", MagicMock(return_value="configured-[bold]-canary"))
    loader = MagicMock(side_effect=failure)
    monkeypatch.setattr(core, "load", loader)
    creator = MagicMock()
    monkeypatch.setattr(runtime.sessions, "create_session", creator)
    runtime.repl.set_session = MagicMock()
    with pytest.raises(click.ClickException) as raised:
        _setup_repl_session(runtime.repl)
    shown = str(raised.value)
    assert "canary" not in shown
    assert "Cannot resume saved session:" in shown
    assert "[REDACTED]" in shown
    assert raised.value.__cause__ is failure
    assert str(failure) == message
    assert loader.call_args.args == ("configured-[bold]-canary",)
    creator.assert_not_called()
    runtime.repl.set_session.assert_not_called()


@pytest.mark.parametrize("stage", ["factory", "provider_loader", "runtime_loader"])
def test_provider_configuration_masks_unknown_auth_header(
    monkeypatch: pytest.MonkeyPatch, stage: str,
) -> None:
    failure = ValueError("Authorization: Bearer unrelated-provider-header-canary")
    loader = MagicMock(side_effect=failure)
    factory = MagicMock(side_effect=failure)
    monkeypatch.setattr("henchman.config.load_settings", loader)
    monkeypatch.setattr("henchman.providers.factory.create_configured_provider", factory)
    with pytest.raises(click.ClickException) as raised:
        if stage == "factory":
            _get_provider(Settings())
        elif stage == "provider_loader":
            _get_provider()
        else:
            _prepare_runtime_context()
    assert str(raised.value) == "Unable to configure provider: Authorization: [REDACTED]"
    assert raised.value.__cause__ is failure
    assert str(failure) == "Authorization: Bearer unrelated-provider-header-canary"
