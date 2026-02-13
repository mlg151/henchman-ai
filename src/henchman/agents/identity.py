from dataclasses import dataclass


@dataclass(frozen=True)
class AgentIdentity:
    """Identity of an agent in the team."""

    id: str
    name: str
    role: str
    description: str

    def __str__(self) -> str:
        return f"{self.name} ({self.role})"
