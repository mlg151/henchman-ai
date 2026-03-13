import pytest

from henchman.tools.builtins.delegate import DelegateTaskTool


@pytest.mark.asyncio
async def test_delegate_task_tool():
    tool = DelegateTaskTool()
    result = await tool.execute(agent="engineer", task="Fix bug")
    assert result.success is True
    assert "Delegation handled" in result.content


def test_delegate_task_tool_kind():
    """Cover DelegateTaskTool.kind property (line 156)."""
    from henchman.tools.base import ToolKind
    from henchman.tools.builtins.delegate import DelegateTaskTool

    tool = DelegateTaskTool()
    assert tool.kind == ToolKind.READ
