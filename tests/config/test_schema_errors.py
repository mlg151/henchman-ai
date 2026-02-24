"""Tests for error cases in config/schema.py."""

import pytest

from henchman.config.schema import AgentConfig


def test_agent_config_no_tools_error() -> None:
    """Test that AgentConfig raises ValueError when tools list is empty."""
    with pytest.raises(ValueError, match="Agent must have at least one tool"):
        AgentConfig(
            name="test",
            role="tester",
            description="Test agent",
            tools=[],  # Empty list should raise error
        )


def test_agent_config_with_tools() -> None:
    """Test that AgentConfig works with non-empty tools list."""
    agent = AgentConfig(
        name="test",
        role="tester",
        description="Test agent",
        tools=["read_file", "write_file"],  # Non-empty list
    )
    assert agent.name == "test"
    assert agent.role == "tester"
    assert agent.tools == ["read_file", "write_file"]
