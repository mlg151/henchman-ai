from collections.abc import AsyncIterator
from typing import Any

from henchman.tools.base import ToolResult
from henchman.tools.registry import ToolRegistry

from .models import Skill


class SkillExecutor:
    """Executes learned skills by running their steps."""

    def __init__(self, tool_registry: ToolRegistry) -> None:
        """Initialize SkillExecutor.

        Args:
            tool_registry: Registry to use for tool execution.
        """
        self.registry = tool_registry

    async def run(
        self, skill: Skill, parameters: dict[str, Any] | None = None
    ) -> AsyncIterator[ToolResult]:
        """Run all steps in a skill.

        Args:
            skill: The Skill to execute.
            parameters: Optional values for parameterized skills.

        Yields:
            ToolResult for each step executed.
        """
        # TODO: Handle parameter substitution in arguments

        for step in skill.steps:
            result = await self.registry.execute(step.tool, step.arguments)
            yield result

            if not result.success:
                break
