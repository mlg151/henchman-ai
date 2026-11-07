"""Shared runtime-truth classifications for discovery surfaces."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final


@dataclass(frozen=True, slots=True)
class DiscoveryCapability:
    """One capability classification surfaced through help, doctor, and tool search."""

    name: str
    classification: str
    summary: str
    detail: str
    aliases: tuple[str, ...] = ()

    @property
    def search_text(self) -> str:
        """Return normalized searchable text for the capability."""

        return " ".join(
            (
                self.name,
                self.classification,
                self.summary,
                *self.aliases,
            )
        ).casefold()


@dataclass(frozen=True, slots=True)
class _CapabilitySpec:
    """Static spec used to resolve one capability at runtime."""

    name: str
    summary: str
    detail: str
    classification: str
    aliases: tuple[str, ...] = ()
    runtime_tool_names: tuple[str, ...] = ()


_DISCOVERY_CAPABILITY_SPECS: Final[tuple[_CapabilitySpec, ...]] = (
    _CapabilitySpec(
        name="operation recovery",
        classification="runtime-dependent",
        summary="/recovery inspects interrupted tool attempts and accepts explicit user decisions.",
        detail=(
            "A bound runtime reports correlated operation states and revision-checked complete/abandon decisions. "
            "Supported regular-tool retries require intact saved inputs and current policy/approval; "
            "orchestration-only delegate retries are unavailable. Unknown effects block continuation. "
            "operations.persistence selects process or durable authority independently of usage accounting. "
            "This does not restore workspace files, provider signatures or background process ownership."
        ),
        aliases=("/recovery", "operations.persistence", "interrupted operation", "explicit retry"),
    ),
    _CapabilitySpec(
        name="content checkpoints",
        classification="runtime-wired",
        summary="User checkpoint commands review captured file/hunk changes and preview decisions.",
        detail=(
            "CLI checkpoint and interactive /checkpoint share list/show/preview/apply/recover/discard/prune. "
            "Captured content is revision-bound; restore conflicts on intervening edits and invalidates plan checks. "
            "POSIX preserves supported modes; Windows NTFS uses an explicit private-ACL content-only policy "
            "pending final native qualification. Runtime capture covers declared write/edit/patch/test targets; "
            "unknown scopes are explicitly unavailable. Textual F8 opens file/hunk review with separate "
            "preview and idle-only Apply controls; native terminal qualification remains pending. "
            "Legacy hash snapshots are non-restorable."
        ),
        aliases=("/checkpoint", "checkpoint", "file review", "hunk review", "restore"),
    ),
    _CapabilitySpec(
        name="task usage",
        classification="runtime-wired",
        summary="/usage shows shared task budgets with separate estimates and reported billing.",
        detail=(
            "REPL and Textual report the active or most recent run's dispatched requests, "
            "settled/held task tokens, remaining limits, accounting lifetime and explicit "
            "price provenance. Unknown costs stay unavailable and currencies stay separate. "
            "This is cumulative task accounting, separate from conversation context occupancy."
        ),
        aliases=("/usage", "remaining budget", "cost provenance", "task tokens"),
    ),
    _CapabilitySpec(
        name="live configuration",
        classification="runtime-wired",
        summary="REPL and Textual inspect active settings and origins through /config and /doctor.",
        detail=(
            "/config view|get KEY reads the retained live snapshot by default; explicit "
            "--scope global|project reads persisted file values. /doctor uses the same live "
            "state. Standalone CLI commands read a fresh startup snapshot. Provider/model "
            "switches retain conversation history and update session origins; file-only "
            "import/export and canonical .henchman writes remain unchanged."
        ),
        aliases=("/config", "/doctor", "settings origins", "session overrides"),
    ),
    _CapabilitySpec(
        name="background subagents",
        classification="runtime-dependent",
        summary="The primary coding agent can launch dynamic background conversations.",
        detail=(
            "invoke_subagent creates independent conversations with custom roles, prompts, and "
            "delegated tool subsets. manage_subagents inspects or cancels them; send_message "
            "queues conversation messages. A bound orchestrator delivers results and input "
            "requests reactively at turn boundaries and joins unfinished work on shutdown. "
            "Standalone tool registration does not bind a runtime."
        ),
        aliases=("invoke_subagent", "manage_subagents", "send_message", "dynamic agents"),
        runtime_tool_names=("invoke_subagent", "manage_subagents", "send_message"),
    ),
    _CapabilitySpec(
        name="background shell",
        classification="runtime-wired",
        summary="Shell commands return tracked background task IDs by default; redirects are supported.",
        detail=(
            "Multiple jobs run concurrently and remain inspectable with task_get, task_list, "
            "task_output, and task_stop while the application is running. Versioned task intent precedes dispatch; "
            "recovered started/running records are outcome_unknown and queued intent never auto-starts. "
            "Saved PIDs do not grant process ownership. Set background=false "
            "for foreground execution and completed output. A successful launch is not a "
            "successful command result. Application shutdown stops unfinished jobs; saved "
            "task records and output do not imply detached execution survives shutdown."
        ),
        aliases=("shell", "background execution", "task_get", "task_list", "task_output", "task_stop"),
        runtime_tool_names=("shell", "task_get", "task_list", "task_output", "task_stop"),
    ),
    _CapabilitySpec(
        name="background python_exec",
        classification="runtime-wired",
        summary="Python snippets return tracked background task IDs by default.",
        detail=(
            "Multiple Python and shell jobs share project-local task tracking. Use task_get, "
            "task_list, task_output, and task_stop while the application is running. Restarted runtimes "
            "report saved started/running jobs as outcome_unknown without replay or process control. "
            "Queued intent remains undispatched; conditional updates preserve concurrent task evidence. Set "
            "background=false for foreground execution and completed output. A successful "
            "launch does not establish a successful result. Application shutdown stops "
            "unfinished jobs; persisted task metadata and logs are not detached execution."
        ),
        aliases=("python_exec", "background execution", "task_get", "task_list", "task_output", "task_stop"),
        runtime_tool_names=("python_exec", "task_get", "task_list", "task_output", "task_stop"),
    ),
    _CapabilitySpec(
        name="goal",
        classification="runtime-dependent",
        summary="Interactive /goal continues work until explicitly completed or paused.",
        detail=(
            "Goals persist with the session. Interactive frontends schedule continuation; "
            "goal_status records completion with a verification summary against the current goal identity. "
            "Headless tool registration alone does not start autonomous continuation."
        ),
        aliases=("/goal", "goal_status", "autonomous continuation"),
        runtime_tool_names=("goal_status",),
    ),
    _CapabilitySpec(
        name="ask_user",
        classification="runtime-dependent",
        summary="REPL and Textual questions use bound input channels; headless calls remain unavailable.",
        detail=(
            "The classic REPL and Textual TUI bind an input handler. Registration alone "
            "does not establish a channel: headless and standalone tools remain "
            "unbound unless an embedder supplies an async handler. No response "
            "is fabricated when input is unavailable."
        ),
        aliases=("ask user", "user input", "clarification"),
        runtime_tool_names=("ask_user",),
    ),
    _CapabilitySpec(
        name="web_search",
        classification="runtime-wired",
        summary="Live builtin web search with truthful dependency and network failure UX.",
        detail=(
            "Tier 1 runtime surface; should appear as live only when the builtin "
            "web_search tool is actually registered."
        ),
        aliases=("search", "duckduckgo", "tier 1"),
        runtime_tool_names=("web_search",),
    ),
    _CapabilitySpec(
        name="mcp",
        classification="runtime-wired",
        summary="MCP auth, status, and bounded catalog refresh are runtime-wired with secret-safe status reporting.",
        detail=(
            "Treat MCP as live only when the runtime exposes both mcp and mcp_auth "
            "tools; status output must report auth presence without printing tokens. "
            "Explicit refresh replaces the connected tool catalog without expanding scoped allowlists. "
            "Pinned SDK 2.3.0 supports tested legacy and 2026-07-28 stdio with bounded frames and "
            "single-dispatch tool calls. Bounded unauthenticated Streamable HTTP supports JSON/SSE from "
            "2025-03-26 through 2026-07-28. Interactive resources/templates/prompts/read/prompt commands "
            "explicitly preview bounded untrusted context without changing conversation history. "
            "Active SDK telemetry is refused; OAuth and context attachment remain pending."
        ),
        aliases=("mcp_auth", "/mcp", "model context protocol"),
        runtime_tool_names=("mcp", "mcp_auth"),
    ),
    _CapabilitySpec(
        name="skill",
        classification="local-only",
        summary="Skill discovery and local inspection are shipped; no remote skill backend is implied.",
        detail=(
            "Skills remain local-only in this variant: discovery and local bundled "
            "inspection are real, but discovery surfaces must not claim a broader "
            "production invocation backend."
        ),
        aliases=("skills", "skill invocation", "metadata"),
    ),
    _CapabilitySpec(
        name="integration blueprints and Slack",
        classification="export-only",
        summary="Integration commands export local blueprints and scaffolds only.",
        detail=(
            "Slack and other integration surfaces in this variant write blueprint "
            "files locally; they do not launch or configure a runtime backend."
        ),
        aliases=("integrations", "integration_blueprints_and_slack", "slack", "export"),
    ),
    _CapabilitySpec(
        name="schedule_cron",
        classification="metadata-only",
        summary="Cron scheduling persists metadata only; no background runner is shipped.",
        detail=(
            "Recurring schedules can be created, listed, paused, resumed, and deleted "
            "as project-local metadata, but no runtime executor is started."
        ),
        aliases=("schedule", "cron", "runner"),
    ),
    _CapabilitySpec(
        name="workflow",
        classification="metadata-only",
        summary="Local workflow definitions and prepared steps; command execution is unavailable.",
        detail=(
            "Workflow run and trigger actions render step previews and record an "
            "execution-unavailable attempt. They do not execute commands, builds, "
            "tests or CI jobs. Trigger and bridge records are local metadata."
        ),
        aliases=("workflows", "workflow execution", "team workflow", "CI"),
        runtime_tool_names=("workflow",),
    ),
    _CapabilitySpec(
        name="plugin marketplace install",
        classification="unavailable",
        summary="Local plugin list/remove flows are real; marketplace install remains unavailable.",
        detail=(
            "Discovery surfaces must distinguish local plugin lifecycle support from "
            "remote marketplace install flows that are not production-ready in this build."
        ),
        aliases=("plugin", "plugin_marketplace_install", "marketplace"),
    ),
    _CapabilitySpec(
        name="agents-platform install",
        classification="unavailable",
        summary="Local agent list/show/publish flows are real; remote registry install remains unavailable.",
        detail=(
            "Agent discovery and local publishing are shipped, but registry-backed "
            "agent installation is still narrowed and must not be presented as live."
        ),
        aliases=("agents", "agents_platform_install", "agent marketplace", "publish"),
    ),
    _CapabilitySpec(
        name="GitHub webhook-helper",
        classification="docs-only",
        summary="GitHub webhook helpers remain docs-only and out of runtime scope in this variant.",
        detail=(
            "Keep webhook-helper treatment narrowed to documentation only here; do "
            "not imply a shipped webhook runtime or build out backend services."
        ),
        aliases=("github_webhook_helper", "webhook helper", "github app"),
    ),
    _CapabilitySpec(
        name="Tier 10 dialogs",
        classification="undiscoverable",
        summary=(
            "Textual workspace dialogs ship in the TUI, but generic discovery/help "
            "surfaces intentionally do not advertise them."
        ),
        detail=(
            "Tier 10 dialogs are implemented inside `henchman chat --tui`, but "
            "they remain runtime-undiscoverable in generic command/help discovery "
            "unless a first-class exposed surface is added."
        ),
        aliases=("tier10", "tier 10", "textual", "dialog", "dialogs"),
    ),
    _CapabilitySpec(
        name="terminal UI controls",
        classification="undiscoverable",
        summary=(
            "Typed terminal UI settings are TUI-scoped controls; generic "
            "discovery/help surfaces intentionally do not advertise them as "
            "generic commands."
        ),
        detail=(
            "ui.output_mode, ui.reduced_motion, ui.detail_density, "
            "ui.keyboard_mode, ui.mouse_capture, and ui.layout.compact_tables "
            "are typed settings configured through the config command. Their "
            "runtime consumers are delivered by the terminal UI workstream; "
            "runtime-scoped discovery must not present them as generic commands."
        ),
        aliases=(
            "ui.output_mode",
            "ui.reduced_motion",
            "ui.detail_density",
            "ui.keyboard_mode",
            "ui.mouse_capture",
            "ui.layout.compact_tables",
            "terminal ui",
            "ui settings",
        ),
    ),
)

_TOOL_NAME_TO_CAPABILITY_NAME: Final[dict[str, str]] = {
    "invoke_subagent": "background subagents",
    "manage_subagents": "background subagents",
    "send_message": "background subagents",
    "ask_user": "ask_user",
    "goal_status": "goal",
    "shell": "background shell",
    "python_exec": "background python_exec",
    "web_search": "web_search",
    "skill": "skill",
    "schedule_cron": "schedule_cron",
    "workflow": "workflow",
    "mcp": "mcp",
    "mcp_auth": "mcp",
}


def build_discovery_capabilities(
    *,
    registered_tool_names: tuple[str, ...] = (),
) -> tuple[DiscoveryCapability, ...]:
    """Return the canonical discovery capability matrix for the current runtime."""

    registered = {name.strip() for name in registered_tool_names if name.strip()}
    resolved: list[DiscoveryCapability] = []

    for spec in _DISCOVERY_CAPABILITY_SPECS:
        classification = spec.classification
        summary = spec.summary
        detail = spec.detail
        if spec.runtime_tool_names and not set(spec.runtime_tool_names).issubset(registered):
            classification = "unavailable"
            summary = f"{spec.name} is not currently registered in this runtime."
            detail = (
                f"Expected runtime-wired surface is missing required tools: "
                f"{', '.join(spec.runtime_tool_names)}."
            )

        resolved.append(
            DiscoveryCapability(
                name=spec.name,
                classification=classification,
                summary=summary,
                detail=detail,
                aliases=spec.aliases,
            )
        )

    return tuple(resolved)


def classify_registered_tool(
    tool_name: str,
    *,
    registered_tool_names: tuple[str, ...] = (),
) -> DiscoveryCapability | None:
    """Return the capability annotation for one registered tool when it has one."""

    capability_name = _TOOL_NAME_TO_CAPABILITY_NAME.get(tool_name)
    if capability_name is None:
        return None

    capabilities = build_discovery_capabilities(registered_tool_names=registered_tool_names)
    return next(
        (capability for capability in capabilities if capability.name == capability_name),
        None,
    )
