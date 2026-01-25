"""
Test suite to improve coverage for specific files.
"""
import pytest
from unittest.mock import Mock, patch


def test_prompts_import():
    """Test prompts.py import."""
    from henchman.cli import prompts
    assert prompts.DEFAULT_SYSTEM_PROMPT is not None
    assert "Henchman" in prompts.DEFAULT_SYSTEM_PROMPT


def test_repl_config():
    """Test ReplConfig."""
    from henchman.cli.repl import ReplConfig
    config = ReplConfig(system_prompt="test")
    assert config.system_prompt == "test"


def test_console_methods():
    """Test console.py methods."""
    from henchman.cli.console import OutputRenderer
    from rich.console import Console
    
    console = Console()
    renderer = OutputRenderer(console)
    
    # Test some basic methods
    assert renderer.console is console
    
    # The missing lines 303-304 are in a _confirm method
    # We can't test private methods directly, but we can test public API


def test_plan_command():
    """Test plan command imports."""
    from henchman.cli.commands.plan import PlanCommand
    # Just test it can be imported
    assert PlanCommand is not None


def test_anthropic_provider():
    """Test AnthropicProvider."""
    from henchman.providers.anthropic import AnthropicProvider
    
    provider = AnthropicProvider(api_key="test")
    assert provider.api_key == "test"
    assert provider.name == "anthropic"
    
    # Test default_model property
    assert hasattr(provider, 'default_model')
    
    # Test max_tokens property  
    assert hasattr(provider, 'max_tokens')


@pytest.mark.asyncio
async def test_anthropic_empty_messages():
    """Test anthropic empty messages validation."""
    from henchman.providers.anthropic import AnthropicProvider
    from henchman.providers.base import Message
    
    provider = AnthropicProvider(api_key="test")
    
    # Mock the anthropic client
    with patch('henchman.providers.anthropic.AsyncAnthropic') as mock_anthropic:
        mock_client = Mock()
        mock_anthropic.return_value = mock_client
        
        # Test empty messages list
        with pytest.raises(ValueError, match="Messages list cannot be empty"):
            async for _ in provider.chat_completion_stream([]):
                pass
        
        # Test message with empty content
        messages = [Message(role="user", content="")]
        with pytest.raises(ValueError, match="cannot have empty content"):
            async for _ in provider.chat_completion_stream(messages):
                pass


def test_repl_basic():
    """Basic Repl test."""
    from henchman.cli.repl import Repl, ReplConfig
    from unittest.mock import Mock
    from rich.console import Console
    
    mock_provider = Mock()
    mock_provider.name = "test"
    
    console = Console()
    repl = Repl(
        provider=mock_provider,
        console=console,
        config=ReplConfig()
    )
    
    assert repl.provider is mock_provider
    assert repl.console is console
    assert repl.config is not None
    assert repl.tool_registry is not None
    assert repl.agent is not None
