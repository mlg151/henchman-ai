"""Tests for the model command."""

from unittest.mock import Mock, patch

import pytest

from henchman.cli.commands import CommandContext
from henchman.cli.commands.model import (
    ModelCommand,
    _get_api_key_for_provider,
    _get_env_var_name,
    _get_env_vars,
    _get_example_config,
)
from henchman.core.agent import Agent
from henchman.core.session import Session
from henchman.providers.base import ModelProvider


class MockProvider(ModelProvider):
    """Mock provider for testing."""

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


@pytest.fixture
def ctx():
    """Create a test command context."""
    console = Mock()
    console.print = Mock()

    session = Session(id="test", project_hash="abc", started="now", last_updated="now")

    agent = Mock(spec=Agent)
    agent.provider = MockProvider("deepseek", "deepseek-chat")
    agent.system_prompt = "Base prompt"

    tool_registry = Mock()

    # Create a mock REPL
    repl = Mock()
    repl.provider = agent.provider

    return CommandContext(
        console=console, session=session, agent=agent, tool_registry=tool_registry, repl=repl
    )


@pytest.mark.asyncio
async def test_model_command_basics():
    """Test basic command properties."""
    cmd = ModelCommand()

    assert cmd.name == "model"
    assert "model" in cmd.description.lower()
    assert cmd.usage == "/model [list|set <provider> [<model>]]"


@pytest.mark.asyncio
async def test_show_current(ctx):
    """Test showing current model configuration."""
    cmd = ModelCommand()

    with (
        patch("henchman.cli.commands.model.load_settings") as mock_load,
        patch("henchman.cli.commands.model.get_default_registry") as mock_registry,
    ):
        # Mock settings
        mock_settings = Mock()
        mock_load.return_value = mock_settings

        # Mock registry
        mock_reg = Mock()
        mock_reg.list_providers.return_value = ["deepseek", "openai", "anthropic"]
        mock_registry.return_value = mock_reg

        await cmd.execute(ctx)

        # Should call show_current
        ctx.console.print.assert_called()
        calls = ctx.console.print.call_args_list
        assert any("Current Configuration" in str(call) for call in calls)
        assert any("deepseek" in str(call) for call in calls)


@pytest.mark.asyncio
async def test_show_current_no_agent():
    """Test showing current model without agent."""
    ctx_no_agent = CommandContext(
        console=Mock(print=Mock()), session=None, agent=None, tool_registry=None
    )

    cmd = ModelCommand()
    await cmd.execute(ctx_no_agent)

    ctx_no_agent.console.print.assert_called_with(
        "[yellow]No active agent. Cannot show current model.[/]"
    )


@pytest.mark.asyncio
async def test_list_providers(ctx):
    """Test listing all providers."""
    cmd = ModelCommand()

    with patch("henchman.cli.commands.model.get_default_registry") as mock_registry:
        mock_reg = Mock()
        mock_reg.list_providers.return_value = ["deepseek", "openai", "anthropic"]

        # Mock provider class
        mock_provider_class = Mock()
        mock_provider_class.__doc__ = "Test provider documentation"
        mock_reg.get.return_value = mock_provider_class

        mock_registry.return_value = mock_reg

        # Call with list argument
        ctx.args = ["list"]
        await cmd.execute(ctx)

        # Should call list_providers
        ctx.console.print.assert_called()
        calls = ctx.console.print.call_args_list
        assert any("Available Providers" in str(call) for call in calls)
        assert any("deepseek" in str(call) for call in calls)
        assert any("openai" in str(call) for call in calls)


@pytest.mark.asyncio
async def test_set_provider_success(ctx):
    """Test successfully switching providers."""
    cmd = ModelCommand()

    with (
        patch("henchman.cli.commands.model.get_default_registry") as mock_registry,
        patch.dict("os.environ", {}, clear=True),
        patch("henchman.cli.commands.model.load_settings") as mock_load,
    ):
        mock_reg = Mock()
        mock_reg.list_providers.return_value = ["deepseek", "openai", "anthropic"]

        # Mock the new provider
        new_provider = MockProvider("openai", "gpt-4")
        mock_reg.create.return_value = new_provider

        mock_registry.return_value = mock_reg

        # Mock settings
        mock_settings = Mock()
        mock_load.return_value = mock_settings

        # Call with set argument
        ctx.args = ["set", "openai"]
        await cmd.execute(ctx)

        # Should update agent and REPL
        assert ctx.agent.provider == new_provider
        assert ctx.repl.provider == new_provider

        # Should print success message
        ctx.console.print.assert_called()
        calls = ctx.console.print.call_args_list
        assert any("Switched from" in str(call) for call in calls)


@pytest.mark.asyncio
async def test_set_provider_not_found(ctx):
    """Test switching to a non-existent provider."""
    cmd = ModelCommand()

    with patch("henchman.cli.commands.model.get_default_registry") as mock_registry:
        mock_reg = Mock()
        mock_reg.list_providers.return_value = ["deepseek", "openai"]
        mock_registry.return_value = mock_reg

        # Call with non-existent provider
        ctx.args = ["set", "nonexistent"]
        await cmd.execute(ctx)

        # Should print error
        ctx.console.print.assert_called()
        calls = ctx.console.print.call_args_list
        assert any("not found" in str(call) for call in calls)


@pytest.mark.asyncio
async def test_set_provider_with_model(ctx):
    """Test switching providers with specific model."""
    cmd = ModelCommand()

    with (
        patch("henchman.cli.commands.model.get_default_registry") as mock_registry,
        patch.dict("os.environ", {}, clear=True),
        patch("henchman.cli.commands.model.load_settings") as mock_load,
    ):
        mock_reg = Mock()
        mock_reg.list_providers.return_value = ["openai"]

        # Mock provider creation with model
        new_provider = MockProvider("openai", "gpt-4-turbo")
        mock_reg.create.return_value = new_provider

        mock_registry.return_value = mock_reg

        # Mock settings with empty api_key attribute
        mock_provider_settings = Mock()
        mock_provider_settings.api_key = (
            None  # This will make _get_api_key_for_provider return None
        )

        mock_settings = Mock()
        mock_settings.providers.openai = mock_provider_settings
        mock_load.return_value = mock_settings

        # Call with provider and model
        ctx.args = ["set", "openai", "gpt-4-turbo"]
        await cmd.execute(ctx)

        # Should create provider with model argument
        # Note: api_key will be empty string because _get_api_key_for_provider returns None
        mock_reg.create.assert_called_with("openai", api_key="", model="gpt-4-turbo")


@pytest.mark.asyncio
async def test_set_provider_no_repl():
    """Test switching providers without REPL context."""
    ctx_no_repl = CommandContext(
        console=Mock(print=Mock()),
        session=Mock(),
        agent=Mock(provider=MockProvider()),
        tool_registry=None,
        repl=None,  # No REPL
    )

    cmd = ModelCommand()
    ctx_no_repl.args = ["set", "openai"]

    await cmd.execute(ctx_no_repl)

    ctx_no_repl.console.print.assert_called_with(
        "[yellow]Cannot switch providers without REPL context.[/]"
    )


@pytest.mark.asyncio
async def test_invalid_usage(ctx):
    """Test invalid command usage."""
    cmd = ModelCommand()

    # Test with invalid arguments
    ctx.args = ["invalid", "args"]
    await cmd.execute(ctx)

    ctx.console.print.assert_called_with("[yellow]Usage: /model [list|set <provider> [<model>]][/]")


@pytest.mark.asyncio
async def test_get_api_key_from_env():
    """Test getting API key from environment variables."""
    with patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}, clear=True):
        api_key = _get_api_key_for_provider("openai")
        assert api_key == "test-key"

    with patch.dict("os.environ", {"HENCHMAN_API_KEY": "generic-key"}, clear=True):
        api_key = _get_api_key_for_provider("openai")
        assert api_key == "generic-key"


@pytest.mark.asyncio
async def test_get_env_var_name():
    """Test getting environment variable names for providers."""
    assert _get_env_var_name("deepseek") == "DEEPSEEK_API_KEY"
    assert _get_env_var_name("openai") == "OPENAI_API_KEY"
    assert _get_env_var_name("anthropic") == "ANTHROPIC_API_KEY"
    assert _get_env_var_name("unknown") == "HENCHMAN_API_KEY"


@pytest.mark.asyncio
async def test_get_example_config():
    """Test getting example configurations."""
    assert "deepseek-chat" in _get_example_config("deepseek")
    assert "gpt-4-turbo" in _get_example_config("openai")
    assert "claude-3" in _get_example_config("anthropic")
    assert "llama2" in _get_example_config("ollama")
    assert _get_example_config("unknown") == "Check provider documentation"


@pytest.mark.asyncio
async def test_get_env_vars():
    """Test getting environment variable descriptions."""
    assert "DEEPSEEK_API_KEY" in _get_env_vars("deepseek")
    assert "OPENAI_API_KEY" in _get_env_vars("openai")
    assert "ANTHROPIC_API_KEY" in _get_env_vars("anthropic")
    assert "OLLAMA_HOST" in _get_env_vars("ollama")
    assert _get_env_vars("unknown") == "Check provider documentation"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
