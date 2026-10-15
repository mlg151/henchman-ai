from unittest.mock import MagicMock

from henchman.agents.config import AgentConfig
from henchman.agents.pool import AgentPool, create_scoped_registry
from henchman.core.eventbus import EventBus
from henchman.providers.base import ModelProvider
from henchman.tools.base import Tool, ToolKind, ToolResult
from henchman.tools.registry import ToolRegistry


class MockTool(Tool):
    def __init__(self, name, kind=ToolKind.READ):
        self._name = name
        self._kind = kind

    @property
    def name(self):
        return self._name

    @property
    def description(self):
        return "mock"

    @property
    def parameters(self):
        return {"type": "object"}

    @property
    def kind(self):
        return self._kind

    async def execute(self, **params):
        return ToolResult(content="ok")


def test_create_scoped_registry():
    parent = ToolRegistry()
    t1 = MockTool("t1")
    t2 = MockTool("t2", ToolKind.WRITE)
    parent.register(t1)
    parent.register(t2)

    scoped = create_scoped_registry(parent, allowed_tools=["t1"], auto_approve=["t1"])

    assert "t1" in scoped.list_tools()
    assert "t2" not in scoped.list_tools()
    assert "t1" in scoped.list_auto_approve_policies()


def test_agent_pool_lazy_init():
    configs = {
        "explorer": AgentConfig(
            name="Explorer", role="explorer", description="desc", tools=["read_file"]
        )
    }
    provider = MagicMock(spec=ModelProvider)
    tool_registry = ToolRegistry()
    tool_registry.register(MockTool("read_file"))
    bus = EventBus()

    pool = AgentPool(configs, provider, None, tool_registry, bus)

    assert len(pool._agents) == 0

    agent = pool.get_agent("explorer")
    assert "explorer" in pool._agents
    assert agent.identity.role == "explorer"
    assert "read_file" in agent.tools.list_tools()


def test_agent_pool_list_agents():
    configs = {
        "explorer": AgentConfig(name="E", role="explorer", description="d", tools=["t"]),
        "disabled": AgentConfig(
            name="D", role="disabled", description="d", tools=["t"], enabled=False
        ),
    }
    pool = AgentPool(configs, MagicMock(), None, ToolRegistry(), EventBus())

    agents = pool.list_agents()
    assert len(agents) == 1
    roles = [a.role for a in agents]
    assert "explorer" in roles


def test_agent_pool_reset():
    configs = {"explorer": AgentConfig(name="E", role="explorer", description="d", tools=["t"])}
    pool = AgentPool(configs, MagicMock(), None, ToolRegistry(), EventBus())

    agent = pool.get_agent("explorer")
    agent.messages.append(MagicMock(role="user", content="hi"))

    pool.reset_agent("explorer")
    # Only system prompt should remain.
    # AgentPool calls get_agent_prompt which uses ROLE_TEMPLATES.

    assert len(agent.messages) == 1
    assert agent.messages[0].role == "system"


def test_create_scoped_registry_with_extra_tools():
    """Test create_scoped_registry with extra_tools including dedup."""
    parent = ToolRegistry()
    t1 = MockTool("t1")
    t2 = MockTool("t2")
    parent.register(t1)
    parent.register(t2)

    # t1 is both in allowed_tools AND extra_tools → should be unregistered first then re-added
    extra_t1 = MockTool("t1", ToolKind.WRITE)
    extra_t3 = MockTool("t3")
    scoped = create_scoped_registry(
        parent, allowed_tools=["t1", "t2"], extra_tools=[extra_t1, extra_t3]
    )

    assert "t1" in scoped.list_tools()
    assert "t2" in scoped.list_tools()
    assert "t3" in scoped.list_tools()
    # t1 was replaced by extra_t1 (WRITE kind)
    assert scoped.get("t1").kind == ToolKind.WRITE


def test_create_scoped_registry_copies_confirmation_handler():
    """Test that confirmation handler is copied from parent."""
    parent = ToolRegistry()
    handler = MagicMock()
    parent.set_confirmation_handler(handler)

    scoped = create_scoped_registry(parent, allowed_tools=[])

    assert scoped._confirmation_handler == handler


def test_agent_pool_get_identity():
    """Test get_identity returns correct identity and raises for unknown roles."""
    configs = {
        "explorer": AgentConfig(
            name="Explorer", role="explorer", description="An explorer", tools=["t"]
        )
    }
    pool = AgentPool(configs, MagicMock(), None, ToolRegistry(), EventBus())

    identity = pool.get_identity("explorer")
    assert identity.role == "explorer"
    assert identity.name == "Explorer"

    import pytest

    with pytest.raises(ValueError, match="not configured"):
        pool.get_identity("unknown_role")


def test_agent_pool_list_active_agents():
    """Test list_active_agents returns only instantiated agents."""
    configs = {
        "explorer": AgentConfig(name="E", role="explorer", description="d", tools=["t"]),
        "planner": AgentConfig(name="P", role="planner", description="d", tools=["t"]),
    }
    pool = AgentPool(configs, MagicMock(), None, ToolRegistry(), EventBus())

    # No agents instantiated yet
    assert pool.list_active_agents() == []

    # Instantiate explorer
    pool.get_agent("explorer")
    active = pool.list_active_agents()
    assert len(active) == 1
    assert active[0].role == "explorer"


def test_agent_pool_reset_all():
    """Test reset_all clears history for all agents."""
    from unittest.mock import MagicMock as MM

    configs = {
        "explorer": AgentConfig(name="E", role="explorer", description="d", tools=["t"]),
        "planner": AgentConfig(name="P", role="planner", description="d", tools=["t"]),
    }
    pool = AgentPool(configs, MagicMock(), None, ToolRegistry(), EventBus())

    # Instantiate agents and add messages
    for role in ["explorer", "planner"]:
        agent = pool.get_agent(role)
        agent.messages.append(MM(role="user", content="hi"))

    pool.reset_all()

    for agent in pool._agents.values():
        # Only system prompt should remain
        assert len(agent.messages) == 1


def test_agent_pool_shutdown():
    """Test shutdown clears all agents."""
    configs = {"explorer": AgentConfig(name="E", role="explorer", description="d", tools=["t"])}
    pool = AgentPool(configs, MagicMock(), None, ToolRegistry(), EventBus())

    pool.get_agent("explorer")
    assert len(pool._agents) == 1

    pool.shutdown()
    assert len(pool._agents) == 0


def test_custom_shell_scope_can_track_jobs_without_gaining_launch_tools():
    """Changing to background defaults must leave custom agents able to follow jobs."""
    parent = ToolRegistry()
    for name in ("shell", "task_get", "task_list", "task_output", "task_stop", "task_create",
                 "python_exec", "goal_status"):
        parent.register(MockTool(name))
    scope = create_scoped_registry(parent, ["shell"])
    assert {"task_get", "task_list", "task_output", "task_stop", "goal_status"} <= set(
        scope.list_tools()
    )
    assert scope.get("python_exec") is None
    assert scope.get("task_create") is None
    scope.unregister("task_stop")
    assert scope.get("task_stop") is None
    parent.unregister("task_get")
    assert scope.get("task_get") is None


def test_read_only_custom_scope_can_complete_goal_without_task_control():
    parent = ToolRegistry()
    for name in ("read_file", "goal_status", "task_get", "task_stop"):
        parent.register(MockTool(name))
    scope = create_scoped_registry(parent, ["read_file"])
    assert scope.get("goal_status") is not None
    assert scope.get("task_stop") is None
    assert scope.get("task_get") is None


def test_custom_job_tracking_discovery_matches_live_scope():
    parent = ToolRegistry()
    for name in ("delegate_task", "python_exec", "task_output", "goal_status"):
        parent.register(MockTool(name))
    configs = {
        "tech_lead": AgentConfig(name="Lead", role="tech_lead", description="Lead", tools=["delegate_task"]),
        "engineer": AgentConfig(name="Engineer", role="engineer", description="Code", tools=["python_exec"]),
    }
    pool = AgentPool(configs, MagicMock(spec=ModelProvider), None, parent, EventBus())
    pool.get_agent("tech_lead")
    assert pool.find_team_tool_roles("task_output", requester_role="tech_lead") == ["engineer"]
    pool.get_agent("engineer")
    assert pool.find_team_tool_roles("task_output", requester_role="tech_lead") == ["engineer"]


async def test_companion_task_stop_preserves_parent_confirmation_denial():
    parent = ToolRegistry()
    parent.register(MockTool("shell", ToolKind.EXECUTE))
    parent.register(MockTool("task_stop", ToolKind.WRITE))

    async def deny(_request):
        return False

    parent.set_confirmation_handler(deny)
    scope = create_scoped_registry(parent, ["shell"])
    result = await scope.execute("task_stop", {"task_id": "existing-job"})
    assert not result.success
    assert "denied" in result.error.lower()
