"""Tests for plan command branch coverage."""

from unittest.mock import Mock

import pytest

from henchman.cli.commands import CommandContext
from henchman.cli.commands.plan import PLAN_MODE_PROMPT, PlanCommand
from henchman.core.agent import Agent
from henchman.core.session import Session


@pytest.mark.asyncio
async def test_plan_toggle_with_duplicate_prompt():
    """Test plan toggle when prompt is already in system prompt."""
    console = Mock()
    session = Session(id="test", project_hash="abc", started="now", last_updated="now")

    # Create agent with PLAN_MODE_PROMPT already in system prompt
    # This simulates a session that was already in plan mode
    agent = Mock(spec=Agent)
    agent.system_prompt = f"Base prompt\n{PLAN_MODE_PROMPT}"

    tool_registry = Mock()

    # Start with plan_mode=True to simulate already being in plan mode
    session.plan_mode = True

    ctx = CommandContext(console=console, session=session, agent=agent, tool_registry=tool_registry)

    cmd = PlanCommand()

    # Toggle OFF (should remove prompt)
    await cmd.execute(ctx)
    assert ctx.session.plan_mode is False
    ctx.tool_registry.set_plan_mode.assert_called_with(enabled=False)
    # The prompt should be removed from system prompt
    # Note: The actual implementation uses replace() which removes all occurrences
    assert PLAN_MODE_PROMPT not in ctx.agent.system_prompt

    # Toggle ON again (should add prompt back)
    await cmd.execute(ctx)
    assert ctx.session.plan_mode is True
    ctx.tool_registry.set_plan_mode.assert_called_with(enabled=True)
    # Prompt should be added back
    assert PLAN_MODE_PROMPT in ctx.agent.system_prompt


@pytest.mark.asyncio
async def test_plan_toggle_multiple_times():
    """Test toggling plan mode multiple times."""
    console = Mock()
    session = Session(id="test", project_hash="abc", started="now", last_updated="now")

    agent = Mock(spec=Agent)
    agent.system_prompt = "Base prompt"

    tool_registry = Mock()

    ctx = CommandContext(console=console, session=session, agent=agent, tool_registry=tool_registry)

    cmd = PlanCommand()

    # Toggle ON
    await cmd.execute(ctx)
    assert ctx.session.plan_mode is True
    assert PLAN_MODE_PROMPT in ctx.agent.system_prompt

    # Toggle OFF
    await cmd.execute(ctx)
    assert ctx.session.plan_mode is False
    assert PLAN_MODE_PROMPT not in ctx.agent.system_prompt

    # Toggle ON again
    await cmd.execute(ctx)
    assert ctx.session.plan_mode is True
    assert PLAN_MODE_PROMPT in ctx.agent.system_prompt

    # Verify console prints
    assert console.print.call_count >= 3


@pytest.mark.asyncio
async def test_plan_mode_with_partial_prompt():
    """Test plan toggle with partial prompt in system prompt."""
    console = Mock()
    session = Session(id="test", project_hash="abc", started="now", last_updated="now")

    # Create agent with partial PLAN_MODE_PROMPT
    partial_prompt = "---\n**PLAN MODE ACTIVE**\nYou are currently in PLAN MODE."
    agent = Mock(spec=Agent)
    agent.system_prompt = f"Base prompt\n{partial_prompt}"

    tool_registry = Mock()

    ctx = CommandContext(console=console, session=session, agent=agent, tool_registry=tool_registry)

    cmd = PlanCommand()

    # Toggle ON - should add full prompt even though partial exists
    await cmd.execute(ctx)
    assert ctx.session.plan_mode is True
    # The full prompt should be added (might create duplication but that's okay)
    assert PLAN_MODE_PROMPT in ctx.agent.system_prompt


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
