from henchman.core.session import SessionMessage
from henchman.providers.base import Message

from .models import Skill, SkillStep


class SkillLearner:
    """Extracts reusable skills from conversation history."""

    def extract_skill(
        self, name: str, description: str, messages: list[Message | SessionMessage]
    ) -> Skill:
        """Create a Skill from a sequence of messages.

        Extracts all tool calls made by the assistant into SkillSteps.

        Args:
            name: Name for the new skill.
            description: Description of what the skill does.
            messages: List of messages to extract from.

        Returns:
            A new Skill object.
        """
        steps = []
        for msg in messages:
            # Handle both Message and SessionMessage
            role = msg.role
            tool_calls = msg.tool_calls

            if role == "assistant" and tool_calls:
                for tc in tool_calls:
                    # SessionMessage tool_calls are dicts, Message tool_calls are ToolCall objects
                    if isinstance(tc, dict):
                        tc_name = tc.get("name", "")
                        tc_args = tc.get("arguments", {})
                    else:
                        tc_name = tc.name
                        tc_args = tc.arguments

                    step = SkillStep(
                        description=f"Call tool {tc_name}",
                        tool=tc_name,
                        arguments=tc_args,
                    )
                    steps.append(step)

        return Skill(name=name, description=description, steps=steps)

