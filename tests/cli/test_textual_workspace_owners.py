"""Workspace overview observes already resolved actors and bound task owners."""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from rich.text import Text

from henchman.advanced.tasks import TaskService
from henchman.agents.identity import AgentIdentity
from henchman.cli.textual_widgets import AgentSummaryPanel, SettingsPanel, TaskListWidget
from henchman.core.agent import Agent
from henchman.tools.builtins.tier6_tools import TaskGetTool
from henchman.tools.registry import ToolRegistry
from tests.advanced.test_task_store import record
from tests.cli.ui_scenarios import InteractionApp


@pytest.fixture
def overview(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    app = InteractionApp(tmp_path)
    # Exercise the production overview only, retaining the deterministic app.
    from henchman.cli.textual_mixins import _WorkspaceMixin
    app._refresh_workspace_widgets = lambda: _WorkspaceMixin._refresh_workspace_widgets(app)
    widgets = {"#agent-summary-panel": AgentSummaryPanel(), "#settings-panels": SettingsPanel(), "#task-list-widget": TaskListWidget()}
    monkeypatch.setattr("henchman.cli.textual_mixins._query_one_or_none", lambda _app, name, _kind: widgets.get(name))
    provider = SimpleNamespace(name="adapter", _accounting_provider_name="configured-alias", default_model="provider-default", request_defaults={"extra_body": {"model": "wire-model"}}, api_key="resolved-credential")
    actor = Agent(provider, tool_registry=ToolRegistry(), identity=AgentIdentity("actor-id", "Selected specialist", "reviewer", "fixture"))
    app.config.agent_role = "reviewer"
    pool = SimpleNamespace(_agents={"reviewer": actor}, get_agent=lambda *_a: pytest.fail("overview constructed an agent"))
    app.core_context = SimpleNamespace(agent=actor, orchestrator=SimpleNamespace(pool=pool), project_root=tmp_path,
                                       session_manager=SimpleNamespace(current=None), tool_registry=ToolRegistry(), mcp_manager=None)
    return app, widgets, actor


def test_resolved_actor_identity_model_and_zero_registered_tools_are_truthful(overview):
    app, widgets, actor = overview
    app._refresh_workspace_widgets()
    text = Text.from_markup(widgets["#agent-summary-panel"].render()).plain
    assert "configured-alias:wire-model" in text
    assert "Selected specialist" in text and "instantiated" in text
    assert "running" not in text.lower() and "Tools: 0" in text
    assert "configured-alias" in widgets["#settings-panels"].render()
    assert not actor.messages


def test_unresolved_role_is_unavailable_without_falling_back_or_constructing(overview):
    app, widgets, _actor = overview
    app.core_context.orchestrator.pool._agents.clear()
    app._refresh_workspace_widgets()
    text = Text.from_markup(widgets["#agent-summary-panel"].render()).plain
    assert "unavailable" in text.lower() and "Tools: unavailable" in text
    assert "wire-model" not in text and "adapter" not in text
    assert "not instantiated" in text


def test_missing_task_owner_does_not_create_cwd_storage_or_claim_empty(overview, monkeypatch):
    app, widgets, _actor = overview
    monkeypatch.setattr(TaskService, "__init__", lambda *_a, **_k: pytest.fail("created ambient task storage"))
    app._refresh_workspace_widgets()
    assert "unavailable" in widgets["#task-list-widget"].render().lower()
    assert not (app.core_context.project_root / ".henchman" / "tasks").exists()


def test_bound_project_task_evidence_does_not_follow_changed_cwd(overview, tmp_path, monkeypatch):
    app, widgets, _actor = overview
    registry = app.core_context.tool_registry
    tool = TaskGetTool()
    tool.bind_runtime(tool_registry=registry, project_root=tmp_path)
    registry.register(tool)
    own = tool._task_service
    own._store.create(dict(record(), title="selected-project-task"))
    foreign = tmp_path / "foreign"
    foreign.mkdir()
    other = TaskService(foreign)
    other._store.create(dict(record(), title="foreign-project-private-task"))
    before = own._index_path.read_bytes(), other._index_path.read_bytes()
    monkeypatch.chdir(foreign)
    app._refresh_workspace_widgets()
    text = widgets["#task-list-widget"].render()
    assert "selected-project-task" in text and "foreign-project" not in text
    assert before == (own._index_path.read_bytes(), other._index_path.read_bytes())


def test_selected_actor_credential_and_unknown_header_project_before_prefixes(overview):
    app, widgets, actor = overview
    actor.identity = AgentIdentity("id", "Authorization: unknown-header-canary", "reviewer", "fixture")
    actor.provider._accounting_provider_name = "resolved-credential"
    actor.provider.request_defaults = {"model": "resolved-credential"}
    app._refresh_workspace_widgets()
    text = "\n".join(Text.from_markup(widget.render()).plain for widget in widgets.values())
    assert "unknown-header-canary" not in text and "resolved-credential" not in text
    assert "REDACTED" in text
    assert actor.identity.name == "Authorization: unknown-header-canary"


def test_tool_count_tracks_existing_scoped_registration_and_unknown(overview):
    from henchman.tools.scoped_registry import ScopedToolRegistry
    app, widgets, actor = overview
    parent = ToolRegistry()
    tool = TaskGetTool()
    parent.register(tool)
    actor.tool_registry = ScopedToolRegistry(parent, ["task_get"])
    app._refresh_workspace_widgets()
    assert "Tools: 1" in widgets["#agent-summary-panel"].render()
    parent.unregister("task_get")
    app._refresh_workspace_widgets()
    assert "Tools: 0" in widgets["#agent-summary-panel"].render()
    actor.tool_registry = None
    app._refresh_workspace_widgets()
    assert "Tools: unavailable" in widgets["#agent-summary-panel"].render()
