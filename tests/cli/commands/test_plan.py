from unittest.mock import Mock

import pytest

from henchman.cli.commands import CommandContext
from henchman.cli.commands.plan import PLAN_MODE_PROMPT, PlanCommand
from henchman.core.agent import Agent
from henchman.core.session import Session


@pytest.fixture
def ctx():
    console = Mock()
    session = Session(
        id="test", project_hash="abc", started="now", last_updated="now"
    )
    agent = Mock(spec=Agent)
    agent.system_prompt = "Base prompt"

    tool_registry = Mock()

    return CommandContext(
        console=console,
        session=session,
        agent=agent,
        tool_registry=tool_registry
    )

@pytest.mark.asyncio

async def test_plan_toggle(ctx):

    cmd = PlanCommand()

    assert cmd.name == "plan"

    assert "Toggle" in cmd.description

    assert cmd.usage == "/plan"



    # Toggle ON


    await cmd.execute(ctx)
    assert ctx.session.plan_mode is True
    ctx.tool_registry.set_plan_mode.assert_called_with(True)
    assert PLAN_MODE_PROMPT in ctx.agent.system_prompt

    # Toggle OFF
    await cmd.execute(ctx)
    assert ctx.session.plan_mode is False
    ctx.tool_registry.set_plan_mode.assert_called_with(False)
    assert PLAN_MODE_PROMPT not in ctx.agent.system_prompt
    assert ctx.agent.system_prompt == "Base prompt"

@pytest.mark.asyncio
async def test_plan_no_session(ctx):
    ctx.session = None
    cmd = PlanCommand()

    await cmd.execute(ctx)
    # Should print warning
    ctx.console.print.assert_called()
    # Should not crash
