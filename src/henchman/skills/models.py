from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class SkillStep(BaseModel):
    """A single step in a skill execution."""
    description: str
    tool: str
    arguments: dict[str, Any]

class SkillParameter(BaseModel):
    """A parameter for a skill."""
    description: str
    required: bool = False
    default: Any | None = None

class Skill(BaseModel):
    """A learned skill that can be replayed."""
    name: str
    description: str
    version: int = 1
    created: datetime = Field(default_factory=datetime.utcnow)
    author: str = "system"
    tags: list[str] = Field(default_factory=list)
    triggers: list[str] = Field(default_factory=list)
    parameters: dict[str, SkillParameter] = Field(default_factory=dict)
    steps: list[SkillStep] = Field(default_factory=list)
