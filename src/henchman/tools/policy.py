"""Centralized effective-policy evaluation for tool invocations.

The plan-mode gate, per-invocation operation effects, and confirmation
requirements resolve from one shared verdict so that every dispatch path
(direct execution, batches, orchestrated delegation, and scoped subagent
registries) enforces the same effective policy.
"""

from __future__ import annotations

from dataclasses import dataclass

from henchman.tools.base import ConfirmationRequest, Tool, ToolKind

#: Effective operation kinds that the Plan Mode boundary blocks.
PLAN_MODE_BLOCKED_KINDS: frozenset[ToolKind] = frozenset(
    {ToolKind.WRITE, ToolKind.EXECUTE, ToolKind.NETWORK}
)


@dataclass(frozen=True)
class PolicyDecision:
    """Centralized effective-policy verdict for one tool invocation.

    Attributes:
        allowed: Whether the invocation passes the Plan Mode boundary.
        denial_reason: The denial error message, or None when allowed.
        confirmation: The confirmation request required for the invocation
            when it is not auto-approved, or None.
        effective_kind: The per-invocation operation effect used for the
            verdict (the static catalog kind unless the tool overrides
            ``execution_kind``).
    """

    allowed: bool
    denial_reason: str | None
    confirmation: ConfirmationRequest | None
    effective_kind: ToolKind


def evaluate_effective_policy(
    tool: Tool,
    params: dict[str, object],
    *,
    plan_mode_active: bool,
    auto_approved: bool,
) -> PolicyDecision:
    """Compute the effective policy for one invocation from a single source.

    The Plan Mode gate applies to the per-invocation effective operation
    effect, not the static catalog kind. Auto-approval suppresses the
    confirmation requirement but never overrides the Plan Mode boundary.

    Args:
        tool: The registered tool being invoked.
        params: The invocation parameters.
        plan_mode_active: Whether the effective Plan Mode boundary is in force
            (including inherited registry ancestry).
        auto_approved: Whether this registry explicitly auto-approves the
            tool (including inherited grants).

    Returns:
        The PolicyDecision for this invocation.
    """
    effective_kind = tool.execution_kind(params)
    if plan_mode_active and effective_kind in PLAN_MODE_BLOCKED_KINDS:
        return PolicyDecision(
            allowed=False,
            denial_reason="Tool disabled in Plan Mode",
            confirmation=None,
            effective_kind=effective_kind,
        )
    return PolicyDecision(
        allowed=True,
        denial_reason=None,
        confirmation=None if auto_approved else tool.needs_confirmation(params),
        effective_kind=effective_kind,
    )
