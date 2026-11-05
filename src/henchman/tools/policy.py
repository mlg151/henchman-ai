"""Centralized effective-policy evaluation for tool invocations.

The plan-mode gate, per-invocation operation effects, and confirmation
requirements resolve from one shared verdict so that every dispatch path
(direct execution, batches, orchestrated delegation, and scoped subagent
registries) enforces the same effective policy.

User-approved confirmations are remembered as session-scoped grants keyed to
the exact approved invocation (tool, effective effect, parameters, risk), so
repeated still-valid authorizations skip the prompt while any changed scope
re-prompts.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from henchman.tools.base import ConfirmationRequest, Tool, ToolKind

#: Effective operation kinds that the Plan Mode boundary blocks.
PLAN_MODE_BLOCKED_KINDS: frozenset[ToolKind] = frozenset(
    {ToolKind.WRITE, ToolKind.EXECUTE, ToolKind.NETWORK}
)


@dataclass(frozen=True, order=True)
class GrantKey:
    """Session-scoped key identifying one user-approved invocation.

    Attributes:
        tool_name: Name of the approved tool.
        effective_kind: The per-invocation operation effect (``ToolKind`` value)
            that was approved, so an escalated effect never reuses the grant.
        params_digest: SHA-256 digest of the canonically serialized parameters,
            so any argument change invalidates the grant.
        risk_level: The confirmed risk level, so a risk change invalidates it.
    """

    tool_name: str
    effective_kind: str
    params_digest: str
    risk_level: str


def grant_key_for(request: ConfirmationRequest, effective_kind: ToolKind) -> GrantKey:
    """Derive the approval-grant key for one confirmation request.

    The key captures the approved scope exactly: tool identity, the effective
    operation effect, the canonical parameter digest, and the risk level.
    Display text such as the description is intentionally excluded.

    Args:
        request: The confirmation request that was (or will be) approved.
        effective_kind: The per-invocation operation effect used for the
            verdict that produced this request.

    Returns:
        The GrantKey for this approved scope.
    """
    canonical = json.dumps(request.params or {}, sort_keys=True, default=str)
    return GrantKey(
        tool_name=request.tool_name,
        effective_kind=effective_kind.value,
        params_digest=hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
        risk_level=request.risk_level,
    )


class ApprovalGrantStore:
    """Holds the user-approved grants for one session scope.

    Grants are keyed to the exact approved invocation. A new session scope
    starts empty; :meth:`clear` invalidates every grant (session boundary).
    """

    def __init__(self) -> None:
        self._grants: set[GrantKey] = set()

    def grant(self, key: GrantKey) -> None:
        """Record a user approval for the given scope."""
        self._grants.add(key)

    def is_granted(self, key: GrantKey) -> bool:
        """Whether the given scope already holds a user approval."""
        return key in self._grants

    def revoke(self, key: GrantKey) -> None:
        """Invalidate one grant, if present."""
        self._grants.discard(key)

    def clear(self) -> None:
        """Invalidate every grant (session boundary)."""
        self._grants.clear()

    def all(self) -> list[GrantKey]:
        """Return the active grants in stable order."""
        return sorted(self._grants)

    def __len__(self) -> int:
        return len(self._grants)


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
