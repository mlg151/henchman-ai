from unittest.mock import Mock, patch

import pytest

from henchman.cli.repl import Repl
from henchman.core.session import Session


@pytest.fixture
def repl():
    # Mock the InputHandler initialization to avoid prompt-toolkit dependencies
    with patch("henchman.cli.repl.InputHandler"):
        provider = Mock()
        provider.__class__.__name__ = "DeepSeekProvider"
        provider.default_model = "deepseek-chat"
        console = Mock()
        repl_instance = Repl(provider=provider, console=console)

        # Mock the agent for token counting
        repl_instance.agent = Mock()
        repl_instance.agent.get_messages_for_api = Mock(return_value=[])

        # Mock tool registry
        repl_instance.tool_registry = Mock()
        repl_instance.tool_registry.list_tools.return_value = ["tool1", "tool2", "tool3"]

        # Mock tool_manager.registry
        repl_instance.tool_manager.registry = repl_instance.tool_registry

        return repl_instance


def test_get_toolbar_status_chat(repl):
    session = Session(id="1", project_hash="abc", started="now", last_updated="now")
    session.plan_mode = False
    repl.session_manager.session = session

    status = repl.output_handler.get_toolbar_status(repl.agent)
    # Check for CHAT
    assert any("CHAT" in text for style, text in status)
    # Check for Provider:Model
    assert any("DeepSeek:deepseek-chat" in text for style, text in status)
    # Check for Tools count
    assert any("Tools: 3" in text for style, text in status)


def test_get_toolbar_status_plan(repl):
    session = Session(id="1", project_hash="abc", started="now", last_updated="now")
    session.plan_mode = True
    repl.session_manager.session = session

    status = repl.output_handler.get_toolbar_status(repl.agent)
    # Check for PLAN MODE
    assert any("PLAN MODE" in text for style, text in status)


def test_get_toolbar_status_no_session(repl):
    repl.session_manager.session = None
    status = repl.output_handler.get_toolbar_status(repl.agent)
    assert any("CHAT" in text for style, text in status)


def test_get_toolbar_status_exception(repl):
    session = Session(id="1", project_hash="abc", started="now", last_updated="now")
    repl.session_manager.session = session
    # Force exception in count_messages
    with patch("henchman.utils.tokens.TokenCounter.count_messages", side_effect=Exception("error")):
        status = repl.output_handler.get_toolbar_status(repl.agent)
        # Should still return mode but maybe skip tokens
        assert any("CHAT" in text for style, text in status)


def test_get_toolbar_status_with_settings(repl):
    """Test status bar with settings for token percentage calculation."""
    session = Session(id="1", project_hash="abc", started="now", last_updated="now")
    session.plan_mode = False
    repl.session_manager.session = session

    # Mock settings with max_tokens (used as fallback when model limit is unknown)
    settings = Mock()
    context = Mock()
    context.max_tokens = 10000
    settings.context = context
    repl.settings = settings
    repl.output_handler.settings = settings
    # Force settings fallback by clearing model name
    repl.output_handler.provider.default_model = None

    # Mock token count to be 3000 (30%)
    with patch("henchman.utils.tokens.TokenCounter.count_messages") as mock_count:
        mock_count.return_value = 3000
        status = repl.output_handler.get_toolbar_status(repl.agent)

    # Should show percentage with green color (less than 50%)
    token_items = [text for style, text in status if "Tokens" in text]
    assert len(token_items) > 0
    assert any("%" in item for item in token_items)
    # Should show "30%" (3000/10000 = 30%)
    assert any("30%" in item for item in token_items)


def test_get_toolbar_status_token_colors(repl):
    """Test token percentage color coding."""
    session = Session(id="1", project_hash="abc", started="now", last_updated="now")
    session.plan_mode = False
    repl.session_manager.session = session

    # Mock settings with max_tokens (used as fallback when model limit is unknown)
    settings = Mock()
    context = Mock()
    context.max_tokens = 10000
    settings.context = context
    repl.settings = settings
    repl.output_handler.settings = settings
    # Force settings fallback by clearing model name
    repl.output_handler.provider.default_model = None

    # Test different percentages
    test_cases = [
        (3000, "green"),  # 30% < 50%
        (6000, "yellow"),  # 60% between 50-75%
        (8000, "red"),  # 80% > 75%
    ]

    for tokens, expected_color in test_cases:
        with patch("henchman.utils.tokens.TokenCounter.count_messages") as mock_count:
            mock_count.return_value = tokens
            status = repl.output_handler.get_toolbar_status(repl.agent)

        # Find token item
        token_item = next((style for style, text in status if "Tokens" in text), None)
        if token_item:
            # Check color is in style string
            assert expected_color in token_item


def test_get_toolbar_status_with_mcp(repl):
    """Test status bar with MCP manager."""
    session = Session(id="1", project_hash="abc", started="now", last_updated="now")
    session.plan_mode = False
    repl.session_manager.session = session

    # Mock MCP manager with clients
    mcp_manager = Mock()
    client1 = Mock()
    client1.is_connected = True
    client2 = Mock()
    client2.is_connected = False
    client3 = Mock()
    client3.is_connected = True
    mcp_manager.clients = {"server1": client1, "server2": client2, "server3": client3}
    repl.mcp_manager = mcp_manager
    repl.output_handler.mcp_manager = mcp_manager

    status = repl.output_handler.get_toolbar_status(repl.agent)

    # Should show MCP status
    mcp_items = [text for style, text in status if "MCP" in text]
    assert len(mcp_items) > 0
    assert any("2/3" in item for item in mcp_items)  # 2 connected out of 3


def test_get_toolbar_status_no_mcp(repl):
    """Test status bar without MCP manager."""
    session = Session(id="1", project_hash="abc", started="now", last_updated="now")
    session.plan_mode = False
    repl.session_manager.session = session
    repl.mcp_manager = None
    repl.output_handler.mcp_manager = None

    status = repl.output_handler.get_toolbar_status(repl.agent)

    # Should not show MCP status
    mcp_items = [text for style, text in status if "MCP" in text]
    assert len(mcp_items) == 0


def test_get_toolbar_status_provider_without_default_model(repl):
    """Test status bar with provider that doesn't have default_model attribute."""
    session = Session(id="1", project_hash="abc", started="now", last_updated="now")
    session.plan_mode = False
    repl.session_manager.session = session

    # Create a custom mock class to test getattr behavior
    class CustomProvider:
        pass

    custom_provider = CustomProvider()
    repl.provider = custom_provider
    repl.output_handler.provider = custom_provider

    status = repl.output_handler.get_toolbar_status(repl.agent)

    # Should show provider name (CustomProvider without "Provider" suffix = "Custom")
    provider_items = [text for style, text in status if "Custom:" in text]
    assert len(provider_items) > 0
    # Should show "unknown" for model
    assert any("unknown" in item for item in provider_items)
