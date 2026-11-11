"""Legacy shortcuts must not copy live or project overrides into global files."""

from io import StringIO
from pathlib import Path
from types import SimpleNamespace

import pytest
from rich.console import Console

from henchman.cli.commands import CommandContext
from henchman.cli.commands.context import ContextCommand
from henchman.cli.commands.mcp import McpCommand
from henchman.cli.commands.theme import _persist_theme_settings
from henchman.config.repository import SettingsRepository, SettingsScope
from henchman.config.runtime import RuntimeSettingsState
from henchman.config.settings import load_settings_snapshot


@pytest.fixture
def context(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(Path, "home", lambda: tmp_path / "home")
    monkeypatch.delenv("HENCHMAN_SETTINGS_PATH", raising=False)
    monkeypatch.setenv("HENCHMAN_PROVIDER", "ollama")
    monkeypatch.setenv("HENCHMAN_MODEL", "environment-model")
    repository = SettingsRepository(tmp_path)
    repository.set("tools.shell_timeout", 17, scope=SettingsScope.PROJECT)
    state = RuntimeSettingsState(load_settings_snapshot(tmp_path))
    state.update({"context": {"max_tokens": 9000}})
    runtime = SimpleNamespace(settings=state.settings, settings_state=state)
    output = StringIO()
    return CommandContext(console=Console(file=output, width=160), repl=runtime), repository, output


def test_theme_persists_only_theme_and_records_live_origin(context):
    ctx, repository, _ = context
    _persist_theme_settings(ctx, "light")
    assert repository.view(scope=SettingsScope.GLOBAL) == {"ui": {"theme": "light"}}
    assert ctx.repl.settings.ui.theme == "light"
    assert ctx.repl.settings_state.snapshot().origins["ui.theme"].scope == "session"
    assert ctx.repl.settings.context.max_tokens == 9000


@pytest.mark.asyncio
@pytest.mark.parametrize("args,expected", [
    (["strategy", "set", "max_tokens", "12000"], {"max_tokens": 12000}),
    (["disable"], {"intelligent_context": False}),
    (["enable"], {"intelligent_context": True}),
])
async def test_context_shortcuts_only_write_named_global_key(context, args, expected):
    ctx, repository, output = context
    ctx.args = args
    await ContextCommand().execute(ctx)
    assert repository.view(scope=SettingsScope.GLOBAL) == {"context": expected}
    assert ctx.repl.settings.context.max_tokens == 9000
    assert "new sessions" in output.getvalue()


@pytest.mark.asyncio
async def test_context_status_displays_runtime_value_after_saved_setting_changes(context):
    ctx, repository, output = context
    repository.set("context.max_tokens", 12000, scope=SettingsScope.GLOBAL)
    await ContextCommand().execute(ctx)
    assert "9,000" in output.getvalue() or "9000" in output.getvalue()
    assert "Live runtime" in output.getvalue()


@pytest.mark.asyncio
async def test_mcp_logging_marks_transient_session_origin_without_file_write(context):
    ctx, repository, _ = context
    ctx.args = ["logging", "on"]
    await McpCommand().execute(ctx)
    assert ctx.repl.settings.ui.mcp_logging
    assert ctx.repl.settings_state.snapshot().origins["ui.mcp_logging"].scope == "session"
    assert repository.view(scope=SettingsScope.GLOBAL) == {}
