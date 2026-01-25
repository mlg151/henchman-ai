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
        id="test",
        project_hash="abc",
        started="now",
        last_updated="now"
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


@pytest.mark.asyncio
async def test_plan_no_tool_registry(ctx):
    """Test plan command when tool_registry is None."""
    ctx.tool_registry = None
    cmd = PlanCommand()

    # Toggle ON
    await cmd.execute(ctx)
    assert ctx.session.plan_mode is True
    # Should not crash even without tool_registry

    # Toggle OFF
    await cmd.execute(ctx)
    assert ctx.session.plan_mode is False


@pytest.mark.asyncio
async def test_plan_no_agent(ctx):
    """Test plan command when agent is None."""
    ctx.agent = None
    cmd = PlanCommand()

    # Toggle ON
    await cmd.execute(ctx)
    assert ctx.session.plan_mode is True
    ctx.tool_registry.set_plan_mode.assert_called_with(True)
    # Should not crash even without agent

    # Toggle OFF
    await cmd.execute(ctx)
    assert ctx.session.plan_mode is False
    ctx.tool_registry.set_plan_mode.assert_called_with(False)


@pytest.mark.asyncio
async def test_plan_prompt_already_in_system_prompt(ctx):
    """Test plan command when PLAN_MODE_PROMPT is already in system prompt."""
    cmd = PlanCommand()

    # First, enable plan mode
    await cmd.execute(ctx)
    assert ctx.session.plan_mode is True
    original_prompt = ctx.agent.system_prompt
    
    # Disable plan mode
    await cmd.execute(ctx)
    assert ctx.session.plan_mode is False
    
    # Enable plan mode again - prompt should not be duplicated
    await cmd.execute(ctx)
    assert ctx.session.plan_mode is True
    # Check that prompt wasn't duplicated
    prompt_count = ctx.agent.system_prompt.count(PLAN_MODE_PROMPT)
    assert prompt_count == 1, f"Prompt appears {prompt_count} times, should appear exactly once"


@pytest.mark.asyncio
async def test_plan_ui_messages(ctx):
    """Test that UI messages are printed correctly."""
    cmd = PlanCommand()

    # Enable plan mode
    await cmd.execute(ctx)
    
    # Check that console.print was called with correct messages
    call_args = [call[0][0] for call in ctx.console.print.call_args_list]
    call_args_str = " ".join(str(arg) for arg in call_args)
    
    assert "Plan Mode ENABLED" in call_args_str
    assert "Write and Execute tools are now disabled" in call_args_str
    
    # Clear mock calls
    ctx.console.print.reset_mock()
    
    # Disable plan mode
    await cmd.execute(ctx)
    
    call_args = [call[0][0] for call in ctx.console.print.call_args_list]
    call_args_str = " ".join(str(arg) for arg in call_args)
    
    assert "Plan Mode DISABLED" in call_args_str

@pytest.mark.asyncio
async def test_plan_mode_prompt_not_duplicated(ctx):
    """Test that plan mode prompt is not duplicated when toggling multiple times."""
    cmd = PlanCommand()
    
    # Enable plan mode
    await cmd.execute(ctx)
    assert ctx.session.plan_mode is True
    first_prompt = ctx.agent.system_prompt
    
    # Disable plan mode
    await cmd.execute(ctx)
    assert ctx.session.plan_mode is False
    
    # Enable plan mode again
    await cmd.execute(ctx)
    assert ctx.session.plan_mode is True
    
    # Check that prompt wasn't duplicated
    prompt_count = ctx.agent.system_prompt.count(PLAN_MODE_PROMPT)
    assert prompt_count == 1, f"Prompt appears {prompt_count} times, should appear exactly once"
    
    # Check that the prompt is the same as the first time
    assert ctx.agent.system_prompt == first_prompt
