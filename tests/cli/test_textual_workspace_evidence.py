"""Workspace and context labels are safe projections of unchanged runtime data."""

from __future__ import annotations

import logging
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from rich.text import Text
from textual.widgets import Tree

from henchman.cli.textual_app import HenchmanTextualApp
from henchman.cli.textual_config import TextualConfig
from henchman.cli.textual_widgets import (
    AgentSummaryPanel,
    MemoryIndicator,
    SettingsPanel,
    SkillPanel,
    TaskListWidget,
    TeamPanel,
)
from henchman.config.schema import Settings
from henchman.tools.builtins.tier6_tools import TaskGetTool
from henchman.tools.registry import ToolRegistry
from tests.advanced.test_task_store import record as task_record


@pytest.fixture
def app(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> HenchmanTextualApp:
    monkeypatch.chdir(tmp_path)
    provider = MagicMock()
    provider.name = "provider-private-canary"
    provider.default_model = "model-private-canary"
    provider.api_key = "private-canary"
    return HenchmanTextualApp(
        provider=provider, settings=Settings(),
        config=TextualConfig(auto_save=False, history_file=tmp_path / "history"),
    )


def test_context_tree_redacts_labels_and_keeps_original_path_data(
    app: HenchmanTextualApp, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "private-canary" / "private-canary.md"
    path.parent.mkdir()
    path.write_text("raw file content")
    loader = MagicMock()
    loader.discover_files.return_value = [path]
    monkeypatch.setattr("henchman.config.context.ContextLoader", lambda: loader)
    tree: Tree[Path] = Tree("Context")
    monkeypatch.setattr(app, "query_one", lambda *_args: tree)

    app._populate_context_tree()

    branch = tree.root.children[0]
    leaf = branch.children[0]
    assert "private-canary" not in branch.label.plain + leaf.label.plain
    assert "[REDACTED]" in branch.label.plain
    assert leaf.label.plain == "[REDACTED].md"
    assert leaf.data is path
    assert leaf.data.read_text() == "raw file content"


@pytest.mark.parametrize("detail", ["private-canary", "Authorization: Bearer unknown-tree-canary"])
def test_context_discovery_error_redacts_before_prefixing_and_logging(
    app: HenchmanTextualApp, monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture, detail: str,
) -> None:
    error = RuntimeError(detail)
    loader = MagicMock()
    loader.discover_files.side_effect = error
    monkeypatch.setattr("henchman.config.context.ContextLoader", lambda: loader)
    tree: Tree[Path] = Tree("Context")
    monkeypatch.setattr(app, "query_one", lambda *_args: tree)

    app._populate_context_tree()

    assert caplog.records
    formatted = "\n".join(logging.Formatter().format(record) for record in caplog.records)
    displayed = tree.root.children[0].label.plain
    assert "canary" not in formatted + displayed
    assert "[REDACTED]" in formatted and "[REDACTED]" in displayed
    assert "RuntimeError" in formatted
    assert all(record.exc_info is None for record in caplog.records)
    assert str(error) == detail


def test_workspace_panels_redact_each_field_before_prefixes_without_mutating_records(
    app: HenchmanTextualApp, monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    panels = {
        "#agent-summary-panel": AgentSummaryPanel(),
        "#memory-indicators": MemoryIndicator(),
        "#task-list-widget": TaskListWidget(),
        "#skill-components": SkillPanel(),
        "#team-components": TeamPanel(),
        "#settings-panels": SettingsPanel(),
    }
    monkeypatch.setattr(app, "query_one", lambda selector, *_args: panels[selector])
    task = SimpleNamespace(
        task_id="task-012345abcdef", status="queued",
        title="Authorization: Bearer unknown-task-canary",
    )
    skill = SimpleNamespace(name="Authorization: Bearer unknown-skill-canary")
    team = SimpleNamespace(name="Authorization: Bearer unknown-team-canary", members=("private-canary",))
    original = deepcopy((task, skill, team))
    registry = ToolRegistry()
    tool = TaskGetTool()
    tool.bind_runtime(tool_registry=registry, project_root=tmp_path)
    registry.register(tool)
    tool._task_service._store.create(dict(task_record(), title=task.title))
    before = tool._task_service._index_path.read_bytes()
    app.core_context = SimpleNamespace(project_root=tmp_path, tool_registry=registry,
                                       session_manager=None, mcp_manager=None)
    monkeypatch.setattr("henchman.cli.textual_mixins.SkillCatalog", lambda: SimpleNamespace(list_skills=lambda: [skill]))
    monkeypatch.setattr("henchman.cli.textual_mixins.TeamWorkspaceService", lambda: SimpleNamespace(list_workspaces=lambda: [team]))
    app.settings.ui.theme = "Authorization: Bearer unknown-theme-canary"
    app.command_history = ["private-canary"]

    app._refresh_workspace_widgets()

    rendered = "\n".join(Text.from_markup(panel.render()).plain for panel in panels.values())
    assert "canary" not in rendered
    assert "[REDACTED]" in rendered
    assert "1 members" in rendered
    assert (task, skill, team) == original
    assert tool._task_service._index_path.read_bytes() == before
    assert app.provider.name == "provider-private-canary"
    assert app.provider.default_model == "model-private-canary"
    assert app.settings.ui.theme == "Authorization: Bearer unknown-theme-canary"
    assert app.command_history == ["private-canary"]


def test_bridge_entries_redact_fields_and_keep_lookup_identity(
    app: HenchmanTextualApp, monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = SimpleNamespace(workspace_id="workspace-private-canary", name="Authorization: Bearer unknown-workspace-canary")
    bridge = SimpleNamespace(
        bridge_id="bridge-private-canary", status="status-private-canary",
        remote_session="Authorization: Bearer unknown-remote-canary",
        created_by="Authorization: Bearer unknown-owner-canary",
    )
    original = deepcopy((workspace, bridge))
    bridges = SimpleNamespace(list_bridges=MagicMock(return_value=[bridge]))
    monkeypatch.setattr("henchman.cli.textual_mixins.TeamWorkspaceService", lambda: SimpleNamespace(list_workspaces=lambda: [workspace]))
    monkeypatch.setattr("henchman.cli.textual_mixins.BridgeSessionService", lambda: bridges)

    entries = app._build_bridge_dialog_entries()

    assert len(entries) == 1
    assert "canary" not in entries[0]
    assert entries[0].count("[REDACTED]") == 5
    assert entries[0] == (
        "Authorization: [REDACTED] / bridge-[REDACTED] (status-[REDACTED])"
        " - Authorization: [REDACTED] by Authorization: [REDACTED]"
    )
    bridges.list_bridges.assert_called_once_with(workspace_id="workspace-private-canary")
    assert (workspace, bridge) == original
