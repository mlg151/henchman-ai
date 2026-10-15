"""Deterministic auxiliary Tier 6 insight services."""

from __future__ import annotations


class AutoDreamService:
    """Generate deterministic ideation prompts from backlog items."""

    def generate(
        self,
        *,
        backlog: list[str],
        recent_findings: list[str] | None = None,
    ) -> tuple[str, ...]:
        """Return dream prompts grounded in current backlog and findings."""

        findings = recent_findings or []
        suffix = findings[0] if findings else "Recent findings unavailable."
        return tuple(f"Dream on {item}: build the next improvement around {suffix}" for item in backlog)


class MagicDocsService:
    """Render lightweight markdown documentation blocks."""

    def render_feature_doc(
        self,
        *,
        title: str,
        summary: str,
        bullets: list[str],
        references: list[str],
    ) -> str:
        """Render one deterministic feature documentation section."""

        bullet_lines = "\n".join(f"- {item}" for item in bullets)
        reference_lines = "\n".join(f"- `{item}`" for item in references)
        return (
            f"## {title}\n\n"
            f"{summary}\n\n"
            f"### Highlights\n{bullet_lines}\n\n"
            f"### References\n{reference_lines}"
        )


class TipsService:
    """Build contextual developer tips from local runtime state."""

    def build_tips(
        self,
        *,
        active_tasks: list[str],
        next_step: str | None,
        disconnected_mcp: list[str] | None = None,
        paused_schedules: list[str] | None = None,
    ) -> tuple[str, ...]:
        """Return deterministic contextual tips."""

        tips: list[str] = []
        if active_tasks:
            tips.append(f"Focus on active tasks first: {', '.join(active_tasks)}.")
        if next_step:
            tips.append(f"Next verified step: {next_step}")
        if disconnected_mcp:
            tips.append(f"Reconnect MCP servers when needed: {', '.join(disconnected_mcp)}.")
        if paused_schedules:
            tips.append(f"Review paused schedules before shipping: {', '.join(paused_schedules)}.")
        return tuple(tips)


class PromptSuggestionService:
    """Suggest next prompts based on current local state."""

    def suggest_next_prompts(
        self,
        *,
        active_tasks: list[str],
        next_step: str | None,
        missing_docs: list[str] | None = None,
    ) -> tuple[str, ...]:
        """Return deterministic next-prompt suggestions."""

        prompts: list[str] = []
        if active_tasks:
            prompts.append(f"Show me the current output for {active_tasks[0]}.")
        if next_step:
            prompts.append(f"Help me execute this next step: {next_step}")
        for doc in missing_docs or []:
            prompts.append(f"Update {doc} to reflect what just shipped.")
        return tuple(prompts)
