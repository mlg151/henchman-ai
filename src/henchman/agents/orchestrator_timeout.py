"""Timeout summary builder for the orchestrator module.

Produces human-readable progress summaries when agents hit turn limits.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .orchestrator_types import (
    MAX_NARRATION_DISPLAY_LENGTH,
    MAX_SUMMARY_LENGTH,
    MAX_TOOL_ARGUMENTS_TO_DISPLAY,
    MAX_TOOL_CALL_DISPLAY_LENGTH,
    RECENT_TOOLS_TO_SHOW,
)

if TYPE_CHECKING:
    from henchman.providers.base import Message, ToolCall


class TimeoutSummaryBuilder:
    """Helper for building timeout summaries for agents."""

    @classmethod
    def build_summary(
        cls: type[TimeoutSummaryBuilder],
        agent: object,
        msg_start: int,
    ) -> str:
        """Build a progress summary from the agent's work so far.

        Called when a specialist hits the turn limit.

        Args:
            agent: The agent that timed out.
            msg_start: Index where this delegation's messages began.

        Returns:
            A formatted progress summary string.
        """
        tools_used: list[str] = []
        files_touched: set[str] = set()
        narration_parts: list[str] = []

        messages: list[Message] = getattr(agent, "messages", [])
        for msg in messages[msg_start:]:
            if msg.role == "assistant":
                _extract_msg_info(msg, tools_used, files_touched, narration_parts)

        return _format_summary(tools_used, files_touched, narration_parts)


def _extract_msg_info(
    msg: Message,
    tools_used: list[str],
    files_touched: set[str],
    narration_parts: list[str],
) -> None:
    """Extract information from a single assistant message."""
    if msg.tool_calls:
        for tc in msg.tool_calls:
            _extract_tool_info(tc, tools_used, files_touched)
    if msg.content:
        narration_parts.append(msg.content[:MAX_SUMMARY_LENGTH])


def _extract_tool_info(
    tc: ToolCall,
    tools_used: list[str],
    files_touched: set[str],
) -> None:
    """Extract tool call information for the timeout summary."""
    tc_args = tc.arguments
    args_str = ", ".join(
        f"{k}={v!r}" for k, v in list(tc_args.items())[:MAX_TOOL_ARGUMENTS_TO_DISPLAY]
    )
    tools_used.append(f"{tc.name}({args_str})")

    path = tc_args.get("path") or tc_args.get("file_path")
    if path and isinstance(path, str):
        files_touched.add(path)


def _format_summary(
    tools_used: list[str],
    files_touched: set[str],
    narration_parts: list[str],
) -> str:
    """Format timeout summary from collected information."""
    lines = ["**Progress at timeout:**"]
    if tools_used:
        lines.append(f"- Tool calls made: {len(tools_used)}")
        lines.extend(
            f"  \u2022 {t[:MAX_TOOL_CALL_DISPLAY_LENGTH]}"
            for t in tools_used[-RECENT_TOOLS_TO_SHOW:]
        )
    if files_touched:
        lines.append(f"- Files touched: {', '.join(sorted(files_touched))}")
    if narration_parts:
        lines.append(
            f"- Last agent output: {narration_parts[-1][:MAX_NARRATION_DISPLAY_LENGTH]}",
        )
    if not tools_used and not narration_parts:
        lines.append("- No significant progress was made.")
    return "\n".join(lines)
