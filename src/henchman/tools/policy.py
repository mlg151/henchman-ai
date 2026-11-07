"""Centralized effective-policy evaluation for tool invocations.

The plan-mode gate, per-invocation operation effects, and confirmation
requirements resolve from one shared verdict so that every dispatch path
(direct execution, batches, orchestrated delegation, and scoped subagent
registries) enforces the same effective policy.

User-approved confirmations are remembered as session-scoped grants keyed to
the registered implementation, effect, parameters, risk, project and physical
targets, so repeated still-valid authorizations skip the prompt while changed
scope requires fresh approval.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from henchman.tools.access_policy import ToolAccessError, ToolAccessPolicy, validate_tool_access
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
        scope_digest: Fingerprint of project identity and physical target scope.
        tool_registration: Unique identity of the registered implementation.
    """

    tool_name: str
    effective_kind: str
    params_digest: str
    risk_level: str
    scope_digest: str = ""
    tool_registration: int = 0


def grant_key_for(
    request: ConfirmationRequest,
    effective_kind: ToolKind,
    *,
    scope_digest: str = "",
    tool_registration: int = 0,
) -> GrantKey:
    """Derive the approval-grant key for one confirmation request.

    The key captures the approved scope exactly: tool identity, the effective
    operation effect, the canonical parameter digest, and the risk level.
    Display text such as the description is intentionally excluded.

    Args:
        request: The confirmation request that was (or will be) approved.
        effective_kind: The per-invocation operation effect used for the
            verdict that produced this request.
        scope_digest: Captured project, physical-target and invocation scope.
        tool_registration: Identity of the actual registered implementation.

    Returns:
        The GrantKey for this approved scope.
    """
    canonical = json.dumps(request.params or {}, sort_keys=True, default=str)
    return GrantKey(
        tool_name=request.tool_name,
        effective_kind=effective_kind.value,
        params_digest=hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
        risk_level=request.risk_level,
        scope_digest=scope_digest,
        tool_registration=tool_registration,
    )


def _path_identity(path: Path) -> tuple[object, ...]:
    """Capture resolution and filesystem identity without reading file contents."""
    resolved = path.resolve()
    identities: list[tuple[str, int, int]] = []
    # Missing creation targets retain their existing ancestor identity.
    for candidate in (resolved, *resolved.parents):
        try:
            info = candidate.stat()
        except FileNotFoundError:
            continue
        identities.append((str(candidate), info.st_dev, info.st_ino))
        if len(identities) == 2:
            break
    return str(path.absolute()), str(resolved), tuple(identities)


def invocation_scope_digest(tool: Tool, params: dict[str, object]) -> str:
    """Fingerprint structured targets and project identity for approval freshness.

    This is an authorization snapshot, not filesystem confinement. Shell/Python
    source and opaque MCP arguments are not interpreted as mediated file paths.
    Checks at actual filesystem/network operations remain separate boundaries.
    """
    cwd = Path.cwd()
    paths = [cwd]
    bound_root = getattr(tool, "_project_root", None)
    if isinstance(bound_root, Path):
        paths.append(bound_root)
    if not tool.name.startswith("mcp_"):
        for key in ("path", "cwd", "repo_path", "output_path", "scan_dir", "file_path", "directory"):
            raw = params.get(key)
            if isinstance(raw, (str, Path)) and raw:
                path = Path(raw)
                # Capture both interpretations: builtins differ on ~ expansion.
                paths.extend((path, path.expanduser()))
        raw_paths = params.get("paths")
        if isinstance(raw_paths, list):
            paths.extend(Path(raw) for raw in raw_paths if isinstance(raw, (str, Path)))
    if tool.name == "patch_apply" and isinstance(params.get("patch"), str):
        from henchman.tools.builtins.patch_apply import PatchParser

        default_path = params.get("path")
        changes = PatchParser(
            str(params["patch"]), default_path if isinstance(default_path, str) else None,
        ).parse()
        paths.extend(Path(path) for path in changes)
    project_identity: tuple[object, ...] | None = None
    for directory in (cwd, *cwd.parents):
        git_entry = directory / ".git"
        if git_entry.exists():
            info = git_entry.stat()
            project_identity = (
                _path_identity(directory), _path_identity(git_entry),
                (info.st_size, info.st_mtime_ns) if git_entry.is_file() else None,
            )
            break
    canonical = json.dumps(
        (params, [_path_identity(path) for path in dict.fromkeys(paths)], project_identity),
        sort_keys=True, default=str,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class ApprovalGrantStore:
    """Holds the user-approved grants for one session scope.

    Grants are keyed to the exact approved invocation. A new session scope
    starts empty; :meth:`clear` invalidates every grant (session boundary).
    """

    def __init__(self) -> None:
        self._grants: set[GrantKey] = set()
        self._generation = 0

    @property
    def generation(self) -> int:
        """Revocation epoch, including resets while an approval is pending."""
        return self._generation

    def grant(self, key: GrantKey) -> None:
        """Record a user approval for the given scope."""
        self._grants.add(key)

    def is_granted(self, key: GrantKey) -> bool:
        """Whether the given scope already holds a user approval."""
        return key in self._grants

    def revoke(self, key: GrantKey) -> None:
        """Invalidate one grant, if present."""
        self._grants.discard(key)
        self._generation += 1

    def clear(self) -> None:
        """Invalidate every grant (session boundary)."""
        self._grants.clear()
        self._generation += 1

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
    access_policies: tuple[ToolAccessPolicy, ...] = (),
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
    try:
        validate_tool_access(tool, params, access_policies)
    except (OSError, RuntimeError, ValueError, ToolAccessError) as exc:
        return PolicyDecision(False, str(exc), None, effective_kind)
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
