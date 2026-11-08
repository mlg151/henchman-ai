"""Private file proposals with explicit, recoverable conflict-checked publication.

This service does not launch agents or confer runtime ownership. Callers must bind
staging and publication to the correct worker and parent before exposing it to
delegated tools. It is not an operating-system sandbox.
"""

from __future__ import annotations

import os
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

from henchman.advanced.checkpoint_codec import identifier
from henchman.advanced.checkpoint_files import WorkspaceFiles
from henchman.advanced.checkpoint_models import (
    CheckpointConflict,
    FileState,
    ReviewFile,
    ReviewResult,
)
from henchman.advanced.checkpoint_store import CheckpointStore
from henchman.advanced.checkpoints import CheckpointService, _hunks, _same
from henchman.utils.evidence_redaction import EvidenceRedactor


@dataclass(frozen=True)
class ChildProposalReview:
    """A frozen proposal revision and its bounded original/proposed content."""

    proposal_id: str
    revision: int
    files: tuple[ReviewFile, ...]


class _ProposalPublisher(CheckpointService):
    """Reuse checkpoint's native no-replace publisher and check invalidation."""

    def __init__(self, files: WorkspaceFiles, store: CheckpointStore, fault: Callable[[str], None]) -> None:
        self._files = files
        self._store = store
        self._fault = fault


class ChildProposalService:
    """Stage explicit text files privately, then review and publish their exact revision.

    Existing parent directories are required. Publication keeps displaced
    originals in a private journal and reports an interrupted or conflicting
    multi-file operation for explicit recovery; it is not an atomic multi-file
    transaction. Ownership and parent authorization belong to the caller.
    """

    def __init__(self, project_root: Path, *, redactor: EvidenceRedactor | None = None,
                 max_file_bytes: int = 1_048_576, max_storage_bytes: int = 67_108_864,
                 exclusions: tuple[str, ...] = (), fault: Callable[[str], None] | None = None) -> None:
        if any(type(value) is not int or value <= 0 for value in (max_file_bytes, max_storage_bytes)):
            raise ValueError("Proposal limits must be positive integers")
        self._policy = redactor if redactor is not None else EvidenceRedactor()
        self._files = WorkspaceFiles(project_root, self._policy, max_file_bytes, exclusions)
        self._store = CheckpointStore(self._files.root, max_storage_bytes, namespace="proposals")
        self._checkpoints = CheckpointService(self._files.root, redactor=self._policy,
                                              max_file_bytes=max_file_bytes, max_storage_bytes=max_storage_bytes,
                                              exclusions=exclusions)
        self._fault = fault or (lambda _stage: None)
        self._publisher = _ProposalPublisher(self._files, self._store, self._fault)

    def _path(self, identity: str, *, plan: bool = False) -> Path:
        if not identifier(identity):
            raise ValueError("Invalid proposal or publication identity")
        return self._store.path / ("plans" if plan else "") / f"{identity}.json"

    def _validate(self, payload: dict[str, Any], identity: str, *, plan: bool) -> None:
        required = {"version", "id", "kind", "project", "repository", "revision", "state", "before", "proposed"}
        required |= {"proposal", "applied", "changed"} if plan else set()
        allowed = required if plan else required | {"last_plan"}
        if (set(payload) not in (required, allowed) or type(payload["version"]) is not int
            or payload["version"] != 1 or payload["id"] != identity or not identifier(identity)
            or payload["kind"] != ("child-publication" if plan else "child-proposal")):
            raise ValueError("Invalid proposal record")
        if (tuple(payload["project"]) != self._files.identity or payload["repository"] != self._files.repository):
            raise CheckpointConflict(reason="Proposal belongs to a different physical project")
        if type(payload["revision"]) is not int or payload["revision"] < 0:
            raise ValueError("Invalid proposal revision")
        if payload["state"] not in ({"preview", "prepared", "done"} if plan else {"draft", "sealed", "integrated"}):
            raise ValueError("Invalid proposal state")
        before, proposed = payload["before"], payload["proposed"]
        if (not isinstance(before, dict) or not 1 <= len(before) <= 256 or not isinstance(proposed, dict)
            or before.keys() != proposed.keys() or len({name.casefold() for name in before}) != len(before)):
            raise ValueError("Invalid proposal scope")
        for name in before:
            if not isinstance(name, str) or self._files.path(name) != name:
                raise ValueError("Invalid proposal path")
            old, new = FileState.from_dict(before[name]), FileState.from_dict(proposed[name])
            expected_mode = old.mode if old.status == "text" else (0o666 if os.name == "nt" else 0o600)
            if (not old.restorable or not new.restorable or not old.parents or old.parents != new.parents
                or (new.status == "text" and new.mode != expected_mode)
                or any(state.content is not None and len(state.content) > self._files.max_file_bytes for state in (old, new))):
                raise ValueError("Unsupported proposal file state")
        if plan:
            if not identifier(payload["proposal"]):
                raise ValueError("Invalid proposal identity")
            applied, changed = payload["applied"], payload["changed"]
            if not isinstance(applied, list) or applied != sorted(before)[:len(applied)]:
                raise ValueError("Invalid proposal publication progress")
            expected_changed = [name for name in applied if before[name] != proposed[name]]
            if changed != expected_changed or (payload["state"] == "preview" and applied):
                raise ValueError("Invalid proposal changed-file progress")
            if payload["state"] == "done" and len(applied) != len(before):
                raise ValueError("Incomplete proposal publication")
        elif "last_plan" in payload and not identifier(payload["last_plan"]):
            raise ValueError("Invalid prior publication identity")

    def _load(self, identity: str, *, plan: bool = False) -> dict[str, Any]:
        self._files.check_root()
        payload = self._store.read(self._path(identity, plan=plan))
        try:
            self._validate(payload, identity, plan=plan)
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError("Invalid persisted proposal authority") from error
        return payload

    def _save(self, payload: dict[str, Any], *, plan: bool = False) -> None:
        self._validate(payload, payload["id"], plan=plan)
        self._store.write(self._path(payload["id"], plan=plan), payload)

    def _plans(self) -> list[dict[str, Any]]:
        return [self._load(path.stem, plan=True) for path in (self._store.path / "plans").glob("*.json")]

    def _assert_idle(self) -> None:
        if any(plan["state"] == "prepared" for plan in self._plans()):
            raise CheckpointConflict(reason="An interrupted proposal publication requires recovery")

    def _assert_no_checkpoint_restore(self) -> None:
        # The checkpoint lock is held before the proposal lock in both services.
        if any(plan["state"] == "prepared" for plan in self._checkpoints._plans()):
            raise CheckpointConflict(reason="An interrupted checkpoint restore requires recovery")

    def _check_content(self, payload: dict[str, Any]) -> None:
        for name in payload["before"]:
            if self._files.excluded(name):
                raise ValueError("Proposal path is now excluded")
            for field in ("before", "proposed"):
                content = FileState.from_dict(payload[field][name]).content
                if content is not None and self._policy.text(content.decode()) != content.decode():
                    raise ValueError("Proposal content now contains a known credential")

    def begin(self, paths: Sequence[str]) -> str:
        """Capture the current explicit scope without changing workspace files."""
        if not isinstance(paths, (list, tuple)) or not 1 <= len(paths) <= 256:
            raise ValueError("Proposal scope must contain between one and 256 files")
        if any(not isinstance(name, str) or self._files.path(name) != name for name in paths):
            raise ValueError("Proposal paths must be canonical")
        if len({name.casefold() for name in paths}) != len(paths) or sum(len(name.encode()) for name in paths) > 65536:
            raise ValueError("Proposal scope contains aliases or exceeds its bound")
        with self._store.lock:
            self._assert_idle()
            before = {}
            for name in sorted(paths):
                state = self._files.state(name)
                if not state.restorable or not state.parents:
                    raise ValueError("Proposal scope contains an unsupported file or missing parent")
                before[name] = state.to_dict()
            identity = uuid4().hex
            payload = {"version": 1, "id": identity, "kind": "child-proposal", "project": self._files.identity,
                       "repository": self._files.repository, "revision": 0, "state": "draft",
                       "before": before, "proposed": dict(before)}
            self._save(payload)
            return identity

    def stage(self, proposal_id: str, path: str, content: str | None) -> None:
        """Replace one proposed text file or propose its deletion, without publishing."""
        if not isinstance(path, str):
            raise ValueError("Proposed path must be text")
        if content is not None and not isinstance(content, str):
            raise ValueError("Proposed content must be text or deletion")
        with self._store.lock:
            self._assert_idle()
            proposal = self._load(proposal_id)
            if proposal["state"] != "draft":
                raise ValueError("Proposal is sealed")
            if path not in proposal["before"] or self._files.excluded(path):
                raise ValueError("Proposed file is outside the current scope")
            old = FileState.from_dict(proposal["before"][path])
            if content is None:
                new = FileState("missing", parents=old.parents)
            else:
                data = content.encode("utf-8")
                if len(data) > self._files.max_file_bytes or "\x00" in content or self._policy.text(content) != content:
                    raise ValueError("Proposed content is oversized, binary or sensitive")
                mode = old.mode if old.status == "text" else (0o666 if os.name == "nt" else 0o600)
                new = FileState("text", data, mode, old.parents)
            proposal["proposed"][path] = new.to_dict()
            proposal["revision"] += 1
            self._save(proposal)

    def seal(self, proposal_id: str) -> None:
        """Freeze staging before a separate caller reviews the proposal."""
        with self._store.lock:
            self._assert_idle()
            proposal = self._load(proposal_id)
            if proposal["state"] != "draft":
                raise ValueError("Proposal is already sealed")
            self._check_content(proposal)
            proposal["state"] = "sealed"
            proposal["revision"] += 1
            self._save(proposal)

    def review(self, proposal_id: str) -> ChildProposalReview:
        """Read the frozen revision; this does not authorize or apply it."""
        with self._store.lock:
            proposal = self._load(proposal_id)
            if proposal["state"] != "sealed":
                raise ValueError("Proposal is not awaiting review")
            self._check_content(proposal)
            files = []
            for name in sorted(proposal["before"]):
                old = FileState.from_dict(proposal["before"][name])
                new = FileState.from_dict(proposal["proposed"][name])
                files.append(ReviewFile(name, old, new, _hunks(old, new), "pending"))
            return ChildProposalReview(proposal_id, proposal["revision"], tuple(files))

    def prepare(self, proposal_id: str, *, revision: int) -> str:
        """Create a revision-bound publication plan after explicit review."""
        with self._store.lock:
            self._assert_idle()
            proposal = self._load(proposal_id)
            if proposal["state"] != "sealed" or type(revision) is not int or revision != proposal["revision"]:
                raise CheckpointConflict(reason="Proposal changed or is no longer awaiting review")
            self._check_content(proposal)
            identity = uuid4().hex
            plan = {"version": 1, "id": identity, "kind": "child-publication", "project": self._files.identity,
                    "repository": self._files.repository, "revision": revision, "state": "preview",
                    "proposal": proposal_id, "before": proposal["before"], "proposed": proposal["proposed"],
                    "applied": [], "changed": []}
            self._save(plan, plan=True)
            return identity

    def _linked(self, plan: dict[str, Any]) -> dict[str, Any]:
        proposal = self._load(plan["proposal"])
        if (proposal["revision"] != plan["revision"] or proposal["before"] != plan["before"]
            or proposal["proposed"] != plan["proposed"]
            or (proposal["state"] != "sealed" and not (
                proposal["state"] == "integrated" and proposal.get("last_plan") == plan["id"]))):
            raise CheckpointConflict(reason="Publication disagrees with the reviewed proposal")
        self._check_content(plan)
        return proposal

    def pending(self) -> tuple[str, ...]:
        with self._store.lock:
            return tuple(sorted(plan["id"] for plan in self._plans() if plan["state"] == "prepared"))

    def apply(self, plan_id: str) -> ReviewResult:
        """Publish only after every current target matches the captured original."""
        with self._checkpoints._store.lock, self._store.lock:
            plan = self._load(plan_id, plan=True)
            proposal = self._linked(plan)
            if plan["state"] == "done":
                return ReviewResult(tuple(plan["changed"]), bool(plan["changed"]))
            self._assert_no_checkpoint_restore()
            self._assert_idle()
            if plan["state"] != "preview":
                raise ValueError("Publication requires explicit recovery")
            conflicts = tuple(name for name, old in plan["before"].items()
                              if not _same(self._files.state(name), FileState.from_dict(old)))
            if conflicts:
                raise CheckpointConflict(tuple(sorted(conflicts)))
            needed = sum(len(FileState.from_dict(plan[field][name]).content or b"")
                         for name in plan["before"] for field in ("before", "proposed"))
            self._store.reserve(needed + 4096)
            self._invalidate(plan)
            plan["state"] = "prepared"
            self._save(plan, plan=True)
            self._fault("prepared")
            return self._publish_with_invalidation(plan, proposal)

    def recover(self, plan_id: str) -> ReviewResult:
        """Resume a prepared publication while retaining conflicting user work."""
        with self._checkpoints._store.lock, self._store.lock:
            plan = self._load(plan_id, plan=True)
            proposal = self._linked(plan)
            if plan["state"] == "done":
                return ReviewResult(tuple(plan["changed"]), bool(plan["changed"]))
            self._assert_no_checkpoint_restore()
            if plan["state"] != "prepared":
                raise ValueError("Publication is not awaiting recovery")
            self._invalidate(plan)
            return self._publish_with_invalidation(plan, proposal)

    def _invalidate(self, plan: dict[str, Any]) -> None:
        from henchman.advanced.plans import PlanExecutionService

        if any(plan["before"][name] != plan["proposed"][name] for name in plan["before"]):
            PlanExecutionService(self._files.root).invalidate_checks(reason="child_proposal_publication")

    def _publish_with_invalidation(self, plan: dict[str, Any], proposal: dict[str, Any]) -> ReviewResult:
        try:
            result = self._publish(plan, proposal)
        except BaseException as primary:
            try:
                self._invalidate(plan)
            except BaseException as cleanup:
                primary.add_note(f"Verification invalidation also failed: {type(cleanup).__name__}")
            raise
        self._invalidate(plan)
        return result

    def _publish(self, plan: dict[str, Any], proposal: dict[str, Any]) -> ReviewResult:
        directory = self._store.path / "plans" / plan["id"]
        if self._files.windows is not None:
            self._files.windows.api.private_directory(directory)
        else:
            directory.mkdir(mode=0o700, exist_ok=True)
        if directory.is_symlink():
            raise ValueError("Publication journal cannot be a symlink")
        self._store.sync_directory(directory.parent)
        for index, name in enumerate(sorted(plan["before"])):
            old = FileState.from_dict(plan["before"][name])
            new = FileState.from_dict(plan["proposed"][name])
            if name not in plan["applied"]:
                if not _same(old, new, parents=False):
                    self._publisher._restore_file(name, old, new, directory, index)
                    plan["changed"].append(name)
                elif not _same(self._files.state(name), old):
                    raise CheckpointConflict((name,))
                plan["applied"].append(name)
                self._save(plan, plan=True)
            elif not _same(self._files.state(name), new):
                raise CheckpointConflict((name,))
        if proposal["state"] == "sealed":
            proposal["state"], proposal["last_plan"] = "integrated", plan["id"]
            self._save(proposal)
            self._fault("recorded")
        plan["state"] = "done"
        self._save(plan, plan=True)
        self._fault("done")
        return ReviewResult(tuple(plan["changed"]), bool(plan["changed"]))

    def retained_originals(self, plan_id: str) -> tuple[str, ...]:
        """Locate retained displaced originals without reading their content."""
        with self._store.lock:
            self._load(plan_id, plan=True)
            return tuple(str(path.relative_to(self._files.root)) for path in sorted(
                (self._store.path / "plans" / plan_id).glob("*.old")))

    def discard(self, proposal_id: str) -> None:
        """Remove proposal evidence only when no publication needs recovery."""
        with self._store.lock:
            self._load(proposal_id)
            plans = [plan for plan in self._plans() if plan["proposal"] == proposal_id]
            if any(plan["state"] == "prepared" for plan in plans):
                raise CheckpointConflict(reason="Interrupted publication must be recovered before discarding originals")
            for plan in plans:
                self._publisher._cleanup(plan["id"])
                self._path(plan["id"], plan=True).unlink()
            self._path(proposal_id).unlink()
            self._store.sync_directory(self._store.path)
