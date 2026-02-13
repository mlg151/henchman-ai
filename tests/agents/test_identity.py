from henchman.agents.identity import AgentIdentity


def test_agent_identity_creation():
    identity = AgentIdentity(
        id="coder-1",
        name="Coder",
        role="coder",
        description="Writes code",
    )
    assert identity.id == "coder-1"
    assert identity.name == "Coder"
    assert identity.role == "coder"
    assert identity.description == "Writes code"


def test_agent_identity_str():
    identity = AgentIdentity(
        id="coder-1",
        name="Coder",
        role="coder",
        description="Writes code",
    )
    assert str(identity) == "Coder (coder)"
