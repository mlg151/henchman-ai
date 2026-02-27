"""Integration tests for the model command."""

from unittest.mock import Mock, patch

import pytest

from henchman.cli.commands.model import ModelCommand
from henchman.cli.repl import Repl
from henchman.core.agent import Agent
from henchman.providers.base import ModelProvider


class MockProvider(ModelProvider):
    """Mock provider for integration testing."""

    def __init__(self, name: str = "mock", model: str = "mock-model"):
        self._name = name
        self._model = model

    @property
    def name(self) -> str:
        return self._name

    @property
    def default_model(self) -> str:
        return self._model

    async def chat_completion_stream(self, messages, tools=None, **kwargs):
        yield Mock(content="mock response")


@pytest.mark.asyncio
async def test_model_command_integration():
    """Test model command integration with REPL and Agent."""
    # Create mocks
    console = Mock()
    console.print = Mock()

    # Create provider
    original_provider = MockProvider("deepseek", "deepseek-chat")

    # Create agent
    agent = Agent(provider=original_provider)

    # Create REPL
    repl = Mock(spec=Repl)
    repl.provider = original_provider
    repl.console = console

    # Create command context
    from henchman.cli.commands import CommandContext

    ctx = CommandContext(console=console, session=None, agent=agent, tool_registry=None, repl=repl)

    # Create model command
    cmd = ModelCommand()

    # Test 1: Show current model
    ctx.args = []
    await cmd.execute(ctx)

    # Should print current configuration
    console.print.assert_called()
    calls = console.print.call_args_list
    assert any("Current Configuration" in str(call) for call in calls)
    assert any("deepseek" in str(call) for call in calls)

    # Reset mock
    console.print.reset_mock()

    # Test 2: List providers
    ctx.args = ["list"]
    with patch("henchman.cli.commands.model.get_default_registry") as mock_registry:
        mock_reg = Mock()
        mock_reg.list_providers.return_value = ["deepseek", "openai", "anthropic"]
        mock_registry.return_value = mock_reg

        await cmd.execute(ctx)

        # Should list providers
        console.print.assert_called()
        calls = console.print.call_args_list
        assert any("Available Providers" in str(call) for call in calls)
        assert any("deepseek" in str(call) for call in calls)
        assert any("openai" in str(call) for call in calls)


@pytest.mark.asyncio
async def test_model_switch_integration():
    """Test switching providers in an integrated context."""
    console = Mock()
    console.print = Mock()

    # Create original provider
    original_provider = MockProvider("deepseek", "deepseek-chat")

    # Create agent
    agent = Agent(provider=original_provider)

    # Create REPL
    repl = Mock(spec=Repl)
    repl.provider = original_provider
    repl.console = console

    # Create command context
    from henchman.cli.commands import CommandContext

    ctx = CommandContext(console=console, session=None, agent=agent, tool_registry=None, repl=repl)

    # Create model command
    cmd = ModelCommand()

    # Test switching to openai
    ctx.args = ["set", "openai"]
    with (
        patch("henchman.cli.commands.model.get_default_registry") as mock_registry,
        patch.dict("os.environ", {}, clear=True),
        patch("henchman.cli.commands.model.load_settings") as mock_load,
    ):
        mock_reg = Mock()
        mock_reg.list_providers.return_value = ["deepseek", "openai"]

        # Mock new provider
        new_provider = MockProvider("openai", "gpt-4")
        mock_reg.create.return_value = new_provider

        mock_registry.return_value = mock_reg

        # Mock settings
        mock_settings = Mock()
        mock_load.return_value = mock_settings

        await cmd.execute(ctx)

        # Verify agent and REPL were updated
        assert agent.provider == new_provider
        assert repl.provider == new_provider

        # Verify success message was printed
        console.print.assert_called()
        calls = console.print.call_args_list
        assert any("Switched from" in str(call) for call in calls)
        assert any("deepseek" in str(call) for call in calls)
        assert any("openai" in str(call) for call in calls)


@pytest.mark.asyncio
async def test_model_command_error_handling():
    """Test error handling in model command."""
    console = Mock()
    console.print = Mock()

    # Create command context without REPL (should fail)
    from henchman.cli.commands import CommandContext

    ctx = CommandContext(
        console=console,
        session=None,
        agent=Mock(spec=Agent, provider=MockProvider()),
        tool_registry=None,
        repl=None,  # No REPL!
    )

    cmd = ModelCommand()

    # Try to switch providers without REPL
    ctx.args = ["set", "openai"]
    await cmd.execute(ctx)

    # Should print error
    console.print.assert_called_with("[yellow]Cannot switch providers without REPL context.[/]")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
