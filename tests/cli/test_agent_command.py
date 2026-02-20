from unittest.mock import AsyncMock, MagicMock

import pytest

from henchman.cli.commands import CommandContext
from henchman.cli.commands.agent import AgentCommand


def _make_ctx(**kwargs):
    ctx = MagicMock(spec=CommandContext)
    ctx.console = MagicMock()
    ctx.repl = MagicMock()
    ctx.repl.orchestrator = MagicMock()
    for k, v in kwargs.items():
        setattr(ctx, k, v)
    return ctx


@pytest.mark.asyncio
async def test_agent_list():
    ctx = _make_ctx(args=["list"])
    ctx.repl.orchestrator.pool.list_agents.return_value = []
    ctx.repl.orchestrator.pool.list_active_agents.return_value = []

    cmd = AgentCommand()
    await cmd.execute(ctx)

    ctx.console.print.assert_called()


@pytest.mark.asyncio
async def test_agent_list_with_agents():
    """Test listing agents when agents exist."""
    identity = MagicMock()
    identity.role = "coder"
    identity.name = "Coder"

    config = MagicMock()
    config.tools = ["read_file", "write_file"]

    ctx = _make_ctx(args=[])
    ctx.repl.orchestrator.pool.list_agents.return_value = [identity]
    ctx.repl.orchestrator.pool.list_active_agents.return_value = [identity]
    ctx.repl.orchestrator.pool.configs = {"coder": config}

    cmd = AgentCommand()
    await cmd.execute(ctx)
    ctx.console.print.assert_called()


@pytest.mark.asyncio
async def test_agent_no_orchestrator():
    """Test execute with no orchestrator on repl."""
    ctx = MagicMock(spec=CommandContext)
    ctx.console = MagicMock()
    ctx.repl = None

    cmd = AgentCommand()
    await cmd.execute(ctx)
    ctx.console.print.assert_called()


@pytest.mark.asyncio
async def test_agent_config_all():
    """Test /agent config with no role (list all)."""
    config = MagicMock()
    config.description = "Writes code"

    ctx = _make_ctx(args=["config"])
    ctx.repl.orchestrator.pool.configs = {"coder": config}

    cmd = AgentCommand()
    await cmd.execute(ctx)
    ctx.console.print.assert_called()


@pytest.mark.asyncio
async def test_agent_config_specific_role():
    """Test /agent config <role>."""
    config = MagicMock()
    config.name = "Coder"
    config.description = "Writes code"
    config.tools = ["read_file"]
    config.can_delegate_to = []
    config.provider = "deepseek"
    config.model = "deepseek-chat"

    ctx = _make_ctx(args=["config", "coder"])
    ctx.repl.orchestrator.pool.configs = {"coder": config}

    cmd = AgentCommand()
    await cmd.execute(ctx)
    ctx.console.print.assert_called()


@pytest.mark.asyncio
async def test_agent_config_unknown_role():
    """Test /agent config <unknown_role>."""
    ctx = _make_ctx(args=["config", "unknown"])
    ctx.repl.orchestrator.pool.configs = {}

    cmd = AgentCommand()
    await cmd.execute(ctx)
    ctx.console.print.assert_called()


@pytest.mark.asyncio
async def test_agent_direct_no_message():
    """Test direct agent talk with no message."""
    ctx = _make_ctx(args=["coder"])

    cmd = AgentCommand()
    await cmd.execute(ctx)
    ctx.console.print.assert_called()


@pytest.mark.asyncio
async def test_agent_direct_no_run_agent_direct():
    """Test direct agent when _run_agent_direct not available."""
    ctx = _make_ctx(args=["coder", "fix bug"])
    del ctx.repl._run_agent_direct

    cmd = AgentCommand()
    await cmd.execute(ctx)
    ctx.console.print.assert_called()


@pytest.mark.asyncio
async def test_agent_direct_message():
    ctx = _make_ctx(args=["coder", "Fix", "this"])
    ctx.repl._run_agent_direct = AsyncMock()

    cmd = AgentCommand()
    await cmd.execute(ctx)

    ctx.repl._run_agent_direct.assert_called_with("coder", "Fix this")


@pytest.mark.asyncio
async def test_agent_command_properties():
    """Test command metadata properties."""
    cmd = AgentCommand()
    assert cmd.name == "agent"
    assert "agent" in cmd.description.lower()
    assert "/agent" in cmd.usage


@pytest.mark.asyncio
async def test_agent_direct_exception():
    """Test direct agent talk when exception is raised."""
    ctx = _make_ctx(args=["coder", "Fix", "this"])
    ctx.repl._run_agent_direct = AsyncMock(side_effect=RuntimeError("agent error"))

    cmd = AgentCommand()
    await cmd.execute(ctx)
    ctx.console.print.assert_called()
