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
    def name(self): return self._name
    @property
    def description(self): return "mock"
    @property
    def parameters(self): return {"type": "object"}
    @property
    def kind(self): return self._kind
    async def execute(self, **params): return ToolResult(content="ok")


def test_create_scoped_registry():
    parent = ToolRegistry()
    t1 = MockTool("t1")
    t2 = MockTool("t2", ToolKind.WRITE)
    parent.register(t1)
    parent.register(t2)

    scoped = create_scoped_registry(
        parent,
        allowed_tools=["t1"],
        auto_approve=["t1"]
    )

    assert "t1" in scoped.list_tools()
    assert "t2" not in scoped.list_tools()
    assert "t1" in scoped.list_auto_approve_policies()


def test_agent_pool_lazy_init():
    configs = {
        "explorer": AgentConfig(
            name="Explorer",
            role="explorer",
            description="desc",
            tools=["read_file"]
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
        "disabled": AgentConfig(name="D", role="disabled", description="d", tools=["t"], enabled=False)
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
