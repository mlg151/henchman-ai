"""Native slash inspection uses live values and protects rendered evidence."""

from io import StringIO
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml
from rich.console import Console

from henchman.cli.commands import CommandContext
from henchman.cli.commands.builtins import get_builtin_commands
from henchman.config.repository import SettingsRepository, SettingsScope
from henchman.config.runtime import RuntimeSettingsState
from henchman.config.settings import load_settings_snapshot


@pytest.fixture
def context(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(Path, "home", lambda: tmp_path / "home")
    for name in ("HENCHMAN_PROVIDER", "HENCHMAN_MODEL", "HENCHMAN_SETTINGS_PATH"):
        monkeypatch.delenv(name, raising=False)
    repository = SettingsRepository(tmp_path)
    repository.set("providers.ollama.model", "disk-model", scope=SettingsScope.PROJECT)
    state = RuntimeSettingsState(load_settings_snapshot(tmp_path))
    state.update({"providers": {"default": "ollama", "ollama": {
        "model": "live-model", "api_key": "known-secret-canary",
        "note": "Authorization: unknown-header-canary",
    }}, "context": {"max_tokens": 9000}})
    output = StringIO()
    runtime = SimpleNamespace(settings=state.settings, settings_state=state)
    ctx = CommandContext(console=Console(file=output, width=200), repl=runtime)
    return ctx, output, repository


async def invoke(ctx, args):
    commands = {command.name: command for command in get_builtin_commands()}
    ctx.args = args[1:]
    await commands[args[0]].execute(ctx)


@pytest.mark.asyncio
@pytest.mark.parametrize("verb", ["get", "view"])
async def test_runtime_config_uses_live_snapshot_with_separate_file_scope(context, verb):
    ctx, output, repository = context
    await invoke(ctx, ["config", verb, "providers.ollama.model"])
    assert yaml.safe_load(output.getvalue()) == {
        "key": "providers.ollama.model", "value": "live-model",
        "requested_scope": "merged", "resolved_scope": "session",
    }
    output.seek(0)
    output.truncate(0)
    await invoke(ctx, ["config", verb, "providers.ollama.model", "--scope", "project"])
    assert yaml.safe_load(output.getvalue())["value"] == "disk-model"
    assert repository.get("providers.ollama.model", scope=SettingsScope.PROJECT) == "disk-model"


@pytest.mark.asyncio
async def test_runtime_config_redacts_nested_secrets_before_rendering(context):
    ctx, output, _ = context
    await invoke(ctx, ["config", "get", "providers.ollama"])
    text = output.getvalue()
    assert "known-secret-canary" not in text
    assert "unknown-header-canary" not in text
    assert "live-model" in text
    assert ctx.repl.settings.providers.ollama["api_key"] == "known-secret-canary"


@pytest.mark.asyncio
@pytest.mark.parametrize("verb", ["set", "unset", "import", "export", "list"])
async def test_runtime_config_does_not_advertise_or_perform_file_writes(context, verb):
    ctx, output, repository = context
    before = repository.view(scope=SettingsScope.PROJECT)
    await invoke(ctx, ["config", verb, "providers.default", "other"])
    assert "view|get" in output.getvalue()
    assert repository.view(scope=SettingsScope.PROJECT) == before


@pytest.mark.asyncio
async def test_runtime_doctor_reports_control_values_and_origins(context):
    ctx, output, _ = context
    await invoke(ctx, ["doctor"])
    text = output.getvalue()
    assert "context.max_tokens" in text and "9000" in text and "session" in text
    assert "providers.default" in text and "ollama" in text
    assert "known-secret-canary" not in text
    assert "unknown-header-canary" not in text
