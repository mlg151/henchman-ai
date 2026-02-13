import pytest
from pydantic import ValidationError

from henchman.agents.config import AgentConfig


def test_agent_config_valid():
    config = AgentConfig(
        name="Coder",
        role="coder",
        description="Writes code",
        tools=["read_file", "write_file"]
    )
    assert config.name == "Coder"
    assert config.role == "coder"
    assert config.tools == ["read_file", "write_file"]
    assert config.enabled is True


def test_agent_config_empty_tools():
    with pytest.raises(ValidationError):
        AgentConfig(
            name="Coder",
            role="coder",
            description="Writes code",
            tools=[]
        )
