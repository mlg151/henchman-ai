import pytest

from henchman.tools.builtins.delegate import DelegateTaskTool
from henchman.tools.registry import ToolRegistry


@pytest.mark.asyncio
async def test_delegate_task_tool_requires_orchestrator() -> None:
    tool = DelegateTaskTool()
    result = await tool.execute(agent="engineer", task="Fix bug")
    assert result.success is False
    assert result.error is not None
    assert "orchestrator" in result.error.lower()
    assert "unavailable" in result.content.lower()


@pytest.mark.asyncio
async def test_registry_execution_cannot_claim_unperformed_delegation() -> None:
    registry = ToolRegistry()
    registry.register(DelegateTaskTool())

    result = await registry.execute("delegate_task", {
        "agent": "explorer", "task": "Explain testing",
        "completion_requirement": "response",
    })

    assert result.success is False
    assert result.error is not None
    assert "orchestrator" in result.error.lower()
    assert "unavailable" in result.content.lower()


def test_delegate_task_tool_kind():
    """Cover DelegateTaskTool.kind property (line 156)."""
    from henchman.tools.base import ToolKind
    from henchman.tools.builtins.delegate import DelegateTaskTool

    tool = DelegateTaskTool()
    assert tool.kind == ToolKind.EXECUTE
