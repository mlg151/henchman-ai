"""Agent identity models for the multi-agent system.

This module defines the AgentIdentity class which represents the identity
of an agent in the team, including its ID, name, role, and description.
"""

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
