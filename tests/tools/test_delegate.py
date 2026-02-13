import pytest

from henchman.tools.builtins.delegate import DelegateTaskTool


@pytest.mark.asyncio
async def test_delegate_task_tool():
    tool = DelegateTaskTool()
    result = await tool.execute(agent="coder", task="Fix bug")
    assert result.success is True
    assert "Delegation handled" in result.content
