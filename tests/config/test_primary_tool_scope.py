"""Saved primary scopes cannot retain authority after explicit tool narrowing."""

from __future__ import annotations

from pathlib import Path

import pytest

from henchman.agents.orchestrator import Orchestrator
from henchman.config import load_settings
from henchman.config.repository import SettingsRepository, SettingsScope
from henchman.providers.ollama import OllamaProvider
from henchman.tools.base import Tool, ToolResult
from henchman.tools.builtins.file_read import ReadFileTool
from henchman.tools.builtins.file_write import WriteFileTool
from henchman.tools.registry import ToolRegistry


class _LateTool(Tool):
    name = "mcp_late"
    description = "Late registration for scope regression coverage"

    async def execute(self, **params: object) -> ToolResult:
        return ToolResult("late")


@pytest.fixture
def repository(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> SettingsRepository:
    """Keep both supported persistence scopes and settings discovery isolated."""
    home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", classmethod(lambda _cls: home))
    monkeypatch.delenv("HENCHMAN_SETTINGS_PATH", raising=False)
    monkeypatch.chdir(tmp_path)
    return SettingsRepository(tmp_path)


@pytest.mark.parametrize("scope", [SettingsScope.PROJECT, SettingsScope.GLOBAL])
async def test_saved_model_override_then_explicit_tools_remains_restricted(
    repository: SettingsRepository, tmp_path: Path, scope: SettingsScope,
) -> None:
    """Ordinary config edits cannot preserve an implicit full-catalog grant."""
    repository.set("agents.agents.tech_lead.model", "selected-model", scope=scope)
    repository.set("agents.agents.tech_lead.tools", ["read_file"], scope=scope)
    # A further unrelated write exercises repeated validation/serialization.
    repository.set("ui.theme", "light", scope=scope)
    settings = load_settings(project_root=tmp_path)
    configured = settings.agents.agents["tech_lead"]
    assert configured.model == "selected-model"
    assert configured.tools == ["read_file"]
    assert "full_tool_access" not in configured.model_dump()

    parent = ToolRegistry()
    parent.register(ReadFileTool())
    parent.register(WriteFileTool())
    orchestrator = Orchestrator(OllamaProvider(), tool_registry=parent, settings=settings)
    parent.register(_LateTool())
    registry = orchestrator.tech_lead.tool_registry
    assert [declaration.name for declaration in registry.get_declarations()] == ["read_file"]
    assert registry.get("write_file") is None
    assert registry.get("mcp_late") is None
    assert registry.get("invoke_subagent") is None
    denied = await registry.execute("write_file", {"path": "forbidden.py", "content": "x=1"})
    assert not denied.success
    assert not (tmp_path / "forbidden.py").exists()


@pytest.mark.parametrize("scope", [SettingsScope.PROJECT, SettingsScope.GLOBAL])
def test_explicit_wildcard_survives_save_and_follows_late_registrations(
    repository: SettingsRepository, tmp_path: Path, scope: SettingsScope,
) -> None:
    """Full access is explicit in the same list that users replace to narrow it."""
    repository.set("agents.agents.tech_lead.tools", ["read_file"], scope=scope)
    repository.set("agents.agents.tech_lead.tools", ["*"], scope=scope)
    repository.set("agents.agents.tech_lead.model", "selected-model", scope=scope)
    settings = load_settings(project_root=tmp_path)
    assert settings.agents.agents["tech_lead"].tools == ["*"]
    parent = ToolRegistry()
    parent.register(ReadFileTool())
    parent.register(WriteFileTool())
    orchestrator = Orchestrator(OllamaProvider(), tool_registry=parent, settings=settings)
    registry = orchestrator.tech_lead.tool_registry
    assert registry.get("write_file") is parent.get("write_file")
    late = _LateTool()
    parent.register(late)
    assert registry.get("mcp_late") is late
    parent.unregister("mcp_late")
    assert registry.get("mcp_late") is None
