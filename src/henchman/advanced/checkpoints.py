"""Content-backed scoped review with conflict checks and recoverable restore.

The caller declares agent-owned paths before execution and completes capture
afterwards. This standalone service does not infer ownership from Git changes,
stage files, rewind conversations, or execute tools. POSIX restore uses durable
displaced originals and no-replace publication, not an unconditional checkout.
"""

from __future__ import annotations

import difflib
import hashlib
import json
import math
import os
import re
import shutil
import stat
import tempfile
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import replace
from pathlib import Path
from typing import Any
from uuid import uuid4

from henchman.advanced.checkpoint_codec import validate
from henchman.advanced.checkpoint_files import WorkspaceFiles
from henchman.advanced.checkpoint_models import (
    CheckpointConflict,
    CheckpointRecord,
    CheckpointReview,
    FileState,
    ReviewFile,
    ReviewHunk,
    ReviewPlan,
    ReviewResult,
    hunk_status,
)
from henchman.advanced.checkpoint_store import CheckpointStore
from henchman.utils.evidence_redaction import EvidenceRedactor

__all__ = ["CheckpointConflict", "CheckpointService"]


def _hunks(before: FileState, after: FileState) -> tuple[ReviewHunk, ...]:
    if hunk_status(before, after) != "supported":
        return ()
    old = (before.content or b"").decode().splitlines(keepends=True)
    new = (after.content or b"").decode().splitlines(keepends=True)
    result: list[ReviewHunk] = []
    for tag, i, j, k, end in difflib.SequenceMatcher(a=old, b=new, autojunk=True).get_opcodes():
        if tag != "equal":
            result.append(ReviewHunk(len(result), i, j, k, end, "".join(old[i:j]), "".join(new[k:end])))
    return tuple(result)


def _same(left: FileState, right: FileState, *, parents: bool = True) -> bool:
    return (left.status, left.content, left.mode) == (right.status, right.content, right.mode) and (
        not parents or left.parents == right.parents
    )


def _hunk_id(hunk: ReviewHunk) -> str:
    return hashlib.sha256(json.dumps([hunk.old_start, hunk.old_end, hunk.before, hunk.after]).encode()).hexdigest()


def _reject_hunks(before: FileState, after: FileState, indices: Sequence[int]) -> FileState:
    available = _hunks(before, after)
    if not indices or not set(indices) <= {hunk.index for hunk in available}:
        raise ValueError("Unsupported or stale text hunk selection")
    lines = (after.content or b"").decode().splitlines(keepends=True)
    for hunk in reversed(available):
        if hunk.index in indices:
            lines[hunk.new_start:hunk.new_end] = hunk.before.splitlines(keepends=True)
    return FileState("text", "".join(lines).encode(), after.mode, after.parents)


class CheckpointService:
    """Bounded private content history; only explicitly supported files restore."""

    def __init__(self, project_root: Path, *, redactor: EvidenceRedactor | None = None,
                 max_file_bytes: int = 1_048_576, max_storage_bytes: int = 67_108_864,
                 max_checkpoints: int = 20, max_age_seconds: float = 30 * 86400,
                 exclusions: tuple[str, ...] = (), fault: Callable[[str], None] | None = None) -> None:
        if any(type(value) is not int or value <= 0 for value in (max_file_bytes, max_storage_bytes, max_checkpoints)):
            raise ValueError("Checkpoint limits must be positive integers")
        if not math.isfinite(max_age_seconds) or max_age_seconds <= 0:
            raise ValueError("Checkpoint retention age must be positive")
        self._policy = redactor if redactor is not None else EvidenceRedactor()
        self._files = WorkspaceFiles(project_root, self._policy, max_file_bytes, exclusions)
        self._store = CheckpointStore(self._files.root, max_storage_bytes)
        self._max_checkpoints = max_checkpoints
        self._max_age_seconds = max_age_seconds
        self._fault = fault or (lambda _stage: None)

    def _path(self, identity: str, *, plan: bool = False) -> Path:
        if not re.fullmatch(r"[0-9a-f]{32}", identity):
            raise ValueError("Invalid checkpoint or plan identity")
        return self._store.path / ("plans" if plan else "") / f"{identity}.json"

    def _load(self, identity: str, *, plan: bool = False) -> dict[str, Any]:
        self._files.check_root()
        payload = self._store.read(self._path(identity, plan=plan))
        try:
            validate(payload, identity, plan=plan, max_file_bytes=self._files.max_file_bytes)
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError("Invalid persisted checkpoint authority") from error
        if tuple(payload["project"]) != self._files.identity or payload["repository"] != self._files.repository:
            raise CheckpointConflict(reason="Checkpoint belongs to a different physical project")
        return payload

    def _save(self, payload: dict[str, Any], *, plan: bool = False) -> None:
        validate(payload, payload["id"], plan=plan, max_file_bytes=self._files.max_file_bytes)
        self._store.write(self._path(payload["id"], plan=plan), payload)

    def _record(self, payload: dict[str, Any]) -> CheckpointRecord:
        return CheckpointRecord(payload["id"], self._policy.text(payload["actor"]), payload["created"], payload["state"], payload["revision"])

    def begin(self, paths: Sequence[str], *, actor: str) -> CheckpointRecord:
        """Capture a bounded explicit edit scope before agent execution."""
        names = sorted({self._files.path(path) for path in paths})
        if not names or len(names) > 256:
            raise ValueError("Checkpoint scope must contain between one and 256 files")
        with self._store.lock:
            self._assert_idle()
            self._prune(reserve=1)
            states = {name: self._files.state(name).to_dict() for name in names}
            payload: dict[str, Any] = {"version": 1, "id": uuid4().hex, "project": self._files.identity,
                       "repository": self._files.repository,
                       "actor": self._policy.text(actor), "created": time.time(), "state": "capturing", "revision": 0,
                       "before": states, "after": {}, "decisions": {}, "accepted_hunks": {}}
            self._save(payload)
            return self._record(payload)

    def complete(self, checkpoint_id: str) -> CheckpointRecord:
        """Capture only the original scope after execution, including absence."""
        with self._store.lock:
            self._assert_idle()
            payload = self._load(checkpoint_id)
            if payload["state"] != "capturing":
                raise ValueError("Checkpoint capture is already complete")
            payload["after"] = {name: self._files.state(name).to_dict() for name in payload["before"]}
            payload["state"] = "ready"
            payload["revision"] += 1
            self._save(payload)
            return self._record(payload)

    def list_checkpoints(self) -> tuple[CheckpointRecord, ...]:
        with self._store.lock:
            return tuple(self._record(payload) for payload in self._records())

    def _records(self) -> list[dict[str, Any]]:
        return sorted((self._load(path.stem) for path in self._store.path.glob("*.json")), key=lambda item: item["created"])

    def _plans(self) -> list[dict[str, Any]]:
        return [self._load(path.stem, plan=True) for path in (self._store.path / "plans").glob("*.json")]

    def _assert_idle(self) -> None:
        if any(plan["state"] == "prepared" for plan in self._plans()):
            raise CheckpointConflict(reason="An interrupted restore requires recovery before another mutation")

    def _prune(self, *, reserve: int = 0) -> None:
        records = self._records()
        plans = self._plans()
        protected = {plan["checkpoint"] for plan in plans if plan["state"] == "prepared"}
        for record in records[:]:
            if record["state"] == "capturing" or record["id"] in protected:
                continue
            if len(records) + reserve <= self._max_checkpoints and time.time() - record["created"] <= self._max_age_seconds:
                continue
            for plan in plans:
                if plan["checkpoint"] == record["id"]:
                    directory = self._store.path / "plans" / plan["id"]
                    if directory.exists():
                        shutil.rmtree(directory)
                    self._path(plan["id"], plan=True).unlink(missing_ok=True)
            self._path(record["id"]).unlink()
            records.remove(record)
        if len(records) + reserve > self._max_checkpoints:
            raise ValueError("Checkpoint retention is full of active captures or interrupted restores")

    def prune(self) -> None:
        """Remove expired completed history; active capture/recovery remains pinned."""
        with self._store.lock:
            self._prune()

    def discard(self, checkpoint_id: str) -> None:
        """Explicitly discard inactive capture/history and its private originals."""
        with self._store.lock:
            self._load(checkpoint_id)
            plans = [plan for plan in self._plans() if plan["checkpoint"] == checkpoint_id]
            if any(plan["state"] == "prepared" for plan in plans):
                raise CheckpointConflict(reason="Interrupted restore must be resolved before discarding its originals")
            for plan in plans:
                self._cleanup(plan["id"])
                self._path(plan["id"], plan=True).unlink()
            self._path(checkpoint_id).unlink()
            self._store.sync_directory(self._store.path)

    def review(self, checkpoint_id: str) -> CheckpointReview:
        with self._store.lock:
            payload = self._load(checkpoint_id)
            return self._review(payload)

    def _review(self, payload: dict[str, Any]) -> CheckpointReview:
        if payload["state"] != "ready":
            raise ValueError("Checkpoint has no after capture yet")
        files = []
        for name in sorted(payload["before"]):
            if self._policy.text(name) != name:
                raise ValueError("Historical checkpoint path now contains a known credential; discard its history")
            before = FileState.from_dict(payload["before"][name])
            after = FileState.from_dict(payload["after"][name])
            # Credential registration can change after capture. Such historical
            # bytes must not be exposed as an ordinary review or restored.
            for label, state in (("before", before), ("after", after)):
                if state.content is not None and self._policy.text(state.content.decode()) != state.content.decode():
                    if label == "before":
                        before = FileState("secret")
                    else:
                        after = FileState("secret")
            accepted = payload["accepted_hunks"].get(name, [])
            hunks = tuple(replace(hunk, accepted=_hunk_id(hunk) in accepted) for hunk in _hunks(before, after))
            files.append(ReviewFile(name, before, after, hunks, payload["decisions"].get(name, "pending")))
        return CheckpointReview(payload["id"], payload["revision"], tuple(files))

    def preview(self, checkpoint_id: str, *, decision: str, paths: Sequence[str] | None = None,
                hunks: Mapping[str, Sequence[int]] | None = None) -> ReviewPlan:
        """Persist an exact, revision-bound decision for later conflict-checked apply."""
        if decision not in {"accept", "reject"}:
            raise ValueError("Checkpoint decision must be accept or reject")
        if paths is not None and hunks is not None:
            raise ValueError("Select files or hunks, not both")
        with self._store.lock:
            self._assert_idle()
            payload = self._load(checkpoint_id)
            review = self._review(payload)
            selected = set(hunks if hunks is not None else paths if paths is not None else payload["before"])
            if not selected or not selected <= payload["before"].keys():
                raise ValueError("Review selection lies outside checkpoint scope")
            changes = {}
            for file in review.files:
                if file.path not in selected:
                    continue
                if not file.restorable:
                    raise ValueError("Selected checkpoint content is non-restorable")
                desired = file.after if decision == "accept" else file.before
                if hunks is not None:
                    indices = set(hunks[file.path])
                    if not indices or not indices <= {hunk.index for hunk in file.hunks}:
                        raise ValueError("Unsupported or stale text hunk selection")
                    if decision == "reject":
                        desired = _reject_hunks(file.before, file.after, sorted(indices))
                # Preserve current parent identity even when restoring original
                # content captured before a directory was created by the agent.
                desired = FileState(desired.status, desired.content, desired.mode, file.after.parents)
                changes[file.path] = {"expected": file.after.to_dict(), "desired": desired.to_dict()}
            identity = uuid4().hex
            plan = {"version": 1, "id": identity, "project": self._files.identity,
                    "repository": self._files.repository, "checkpoint": checkpoint_id,
                    "revision": review.revision, "decision": decision, "state": "preview", "changes": changes,
                    "applied": [], "changed": [], "created": time.time(),
                    "hunks": {path: sorted(set(indices)) for path, indices in hunks.items()} if hunks is not None else None}
            self._save(plan, plan=True)
            return ReviewPlan(identity, checkpoint_id, review.revision, decision, tuple(sorted(selected)))

    def pending_restores(self) -> tuple[str, ...]:
        with self._store.lock:
            return tuple(plan["id"] for plan in self._plans() if plan["state"] == "prepared")

    def apply(self, plan_id: str) -> ReviewResult:
        """Apply an issued preview after checking every selected current file."""
        with self._store.lock:
            plan = self._load(plan_id, plan=True)
            payload = self._load(plan["checkpoint"])
            if plan["state"] == "done":
                return ReviewResult(tuple(plan["changed"]), bool(plan["changed"]))
            self._assert_idle()
            if plan["state"] != "preview" or payload["revision"] != plan["revision"]:
                raise CheckpointConflict(reason="Review changed or restore requires explicit recovery")
            self._validate_decision(plan, payload)
            conflicts = tuple(name for name, change in plan["changes"].items()
                              if not _same(self._files.state(name), FileState.from_dict(change["expected"])))
            if conflicts:
                raise CheckpointConflict(conflicts)
            self._check_plan_content(plan)
            needed = sum(len(FileState.from_dict(change[side]).content or b"")
                         for change in plan["changes"].values() for side in ("expected", "desired"))
            self._store.reserve(needed + 4096)
            self._invalidate_checks(plan)
            plan["state"] = "prepared"
            self._save(plan, plan=True)
            self._fault("prepared")
            try:
                return self._restore(plan, payload)
            finally:
                self._invalidate_checks(plan)

    def recover(self, plan_id: str) -> ReviewResult:
        """Resume a durable restore; conflicting user work remains untouched."""
        with self._store.lock:
            plan = self._load(plan_id, plan=True)
            payload = self._load(plan["checkpoint"])
            if plan["state"] == "done":
                return ReviewResult(tuple(plan["changed"]), bool(plan["changed"]))
            if plan["state"] != "prepared":
                raise ValueError("Plan is not an interrupted restore")
            if payload["revision"] not in {plan["revision"], plan["revision"] + 1}:
                raise CheckpointConflict(reason="Checkpoint revision changed during recovery")
            if payload["revision"] == plan["revision"] + 1 and payload.get("last_plan") != plan_id:
                raise CheckpointConflict(reason="A different decision changed checkpoint recovery authority")
            self._validate_decision(plan, payload)
            self._check_plan_content(plan)
            self._invalidate_checks(plan)
            try:
                return self._restore(plan, payload)
            finally:
                self._invalidate_checks(plan)

    def _invalidate_checks(self, plan: dict[str, Any]) -> None:
        """Revoke checks before mutation and supersede concurrent observations."""
        from henchman.advanced.plans import PlanExecutionService

        if any(change["expected"] != change["desired"] for change in plan["changes"].values()):
            PlanExecutionService(self._files.root).invalidate_checks()

    def _validate_decision(self, plan: dict[str, Any], payload: dict[str, Any]) -> None:
        if not plan["changes"].keys() <= payload["before"].keys():
            raise ValueError("Restore plan escapes captured scope")
        for name, change in plan["changes"].items():
            expected = FileState.from_dict(change["expected"])
            desired = FileState.from_dict(change["desired"])
            before = FileState.from_dict(payload["before"][name])
            if payload["revision"] == plan["revision"]:
                if not _same(expected, FileState.from_dict(payload["after"][name])):
                    raise ValueError("Restore expectation disagrees with captured after state")
            elif not _same(desired, FileState.from_dict(payload["after"][name])):
                raise ValueError("Completed decision disagrees with checkpoint state")
            target = expected if plan["decision"] == "accept" else before
            if plan["hunks"] is not None:
                rejected = _reject_hunks(before, expected, plan["hunks"][name])
                if plan["decision"] == "reject":
                    target = rejected
            if not _same(target, desired, parents=False):
                raise ValueError("Restore content disagrees with selected decision")

    def retained_originals(self, plan_id: str) -> tuple[str, ...]:
        """Locate private displaced originals; never expose their possibly edited bytes."""
        with self._store.lock:
            self._load(plan_id, plan=True)
            return tuple(str(path.relative_to(self._files.root)) for path in sorted(
                (self._store.path / "plans" / plan_id).glob("*.old")))

    def _cleanup(self, plan_id: str) -> None:
        directory = self._store.path / "plans" / plan_id
        if directory.exists():
            shutil.rmtree(directory)
            self._store.sync_directory(directory.parent)

    def _check_plan_content(self, plan: dict[str, Any]) -> None:
        for name, change in plan["changes"].items():
            if self._files.excluded(name):
                raise ValueError("Selected checkpoint path is now excluded")
            for side in ("expected", "desired"):
                state = FileState.from_dict(change[side])
                if not state.restorable or (state.content is not None and self._policy.text(state.content.decode()) != state.content.decode()):
                    raise ValueError("Selected checkpoint content is now non-restorable")

    def _restore(self, plan: dict[str, Any], payload: dict[str, Any]) -> ReviewResult:
        directory = self._store.path / "plans" / plan["id"]
        directory.mkdir(mode=0o700, exist_ok=True)
        if directory.is_symlink():
            raise ValueError("Restore journal directory cannot be a symlink")
        for index, (name, change) in enumerate(sorted(plan["changes"].items())):
            expected = FileState.from_dict(change["expected"])
            desired = FileState.from_dict(change["desired"])
            if name not in plan["applied"]:
                if not _same(expected, desired, parents=False):
                    self._restore_file(name, expected, desired, directory, index)
                    plan["changed"].append(name)
                elif not _same(self._files.state(name), expected):
                    raise CheckpointConflict((name,))
                plan["applied"].append(name)
                self._save(plan, plan=True)
            elif not _same(self._files.state(name), desired):
                raise CheckpointConflict((name,))
        if payload["revision"] == plan["revision"]:
            for name, change in plan["changes"].items():
                before = FileState.from_dict(payload["before"][name])
                expected = FileState.from_dict(change["expected"])
                selected = {_hunk_id(hunk) for hunk in _hunks(before, expected)
                            if plan["hunks"] is None or hunk.index in plan["hunks"][name]}
                accepted = set(payload["accepted_hunks"].get(name, []))
                accepted = accepted | selected if plan["decision"] == "accept" else accepted - selected
                payload["accepted_hunks"][name] = sorted(accepted)
                payload["after"][name] = change["desired"]
                payload["decisions"][name] = "partial" if plan["hunks"] is not None else plan["decision"]
            payload["revision"] += 1
            payload["last_plan"] = plan["id"]
            self._save(payload)
            self._fault("recorded")
        plan["state"] = "done"
        self._save(plan, plan=True)
        self._fault("done")
        # Keep displaced inodes until explicit history discard/retention. An
        # already-open writer can still modify them after pathname replacement.
        return ReviewResult(tuple(plan["changed"]), bool(plan["changed"]))

    def _restore_file(self, name: str, expected: FileState, desired: FileState, directory: Path, index: int) -> None:
        backup = directory / f"{index}.old"
        staged = directory / f"{index}.new"
        with self._files.parent(name) as (parent, leaf, parents):
            if parents != expected.parents:
                raise CheckpointConflict((name,), "Checkpoint parent directory changed")
            for partial in directory.glob(f"{index}.partial-*"):
                partial_info = partial.lstat()
                if not stat.S_ISREG(partial_info.st_mode):
                    raise ValueError("Unsupported partial restore object")
                if partial_info.st_nlink > 1:
                    if not staged.exists():
                        raise ValueError("Partial restore object has unexpected aliases")
                    staged_info = staged.lstat()
                    if (partial_info.st_dev, partial_info.st_ino, partial_info.st_nlink) != (
                        staged_info.st_dev, staged_info.st_ino, 2,
                    ):
                        raise ValueError("Partial restore object has unexpected aliases")
                partial.unlink()
            if staged.exists():
                descriptor = os.open(staged, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
                try:
                    staged_state = self._files.read_descriptor(descriptor, allowed_links=(1, 2))
                finally:
                    os.close(descriptor)
                if not _same(staged_state, desired, parents=False):
                    raise ValueError("Staged restore content or mode is corrupt; workspace left untouched")
            if expected.status == "text" and not backup.exists():
                if not _same(self._files.state(name), expected):
                    raise CheckpointConflict((name,))
                self._fault("before_displace")
                os.rename(leaf, backup, src_dir_fd=parent)
                os.fsync(parent)
                self._store.sync_directory(directory)
                self._fault("displaced")
            if backup.exists():
                descriptor = os.open(backup, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
                try:
                    displaced = self._files.read_descriptor(descriptor)
                finally:
                    os.close(descriptor)
                if not _same(displaced, expected, parents=False):
                    # A writer won the check/rename race. Restore its bytes only
                    # into an absent name; otherwise retain the private backup.
                    try:
                        os.link(backup, leaf, dst_dir_fd=parent, follow_symlinks=False)
                    except FileExistsError:
                        pass
                    else:
                        backup.unlink()
                        os.fsync(parent)
                    raise CheckpointConflict((name,), "Intervening edit retained; restore requires conflict resolution")
            if staged.exists():
                staged_info = staged.lstat()
                if not stat.S_ISREG(staged_info.st_mode):
                    raise ValueError("Unsupported staged restore object")
                try:
                    current_info = os.stat(leaf, dir_fd=parent, follow_symlinks=False)
                except FileNotFoundError:
                    current_info = None
                if current_info is not None and (staged_info.st_dev, staged_info.st_ino) == (current_info.st_dev, current_info.st_ino):
                    # Publication completed but the process died before removing
                    # its staging link. Drop only that owned alias before checks.
                    staged.unlink()
            current = self._files.state(name)
            if _same(current, desired):
                return  # Process died after publication but before journal update.
            if current.status != "missing":
                raise CheckpointConflict((name,))
            if desired.status == "text":
                if staged.exists() and staged.lstat().st_nlink != 1:
                    raise ValueError("Staged restore object has unexpected aliases")
                if not staged.exists():
                    descriptor, temporary = tempfile.mkstemp(prefix=f"{index}.partial-", dir=directory)
                    try:
                        with os.fdopen(descriptor, "wb") as handle:
                            handle.write(desired.content or b"")
                            handle.flush()
                            os.fchmod(handle.fileno(), desired.mode if desired.mode is not None else 0o600)
                            os.fsync(handle.fileno())
                        os.link(temporary, staged, follow_symlinks=False)
                        self._fault("stage_linked")
                    finally:
                        Path(temporary).unlink(missing_ok=True)
                self._store.sync_directory(directory)
                self._fault("staged")
                self._fault("before_publish")
                try:
                    os.link(staged, leaf, dst_dir_fd=parent, follow_symlinks=False)
                except FileExistsError as error:
                    raise CheckpointConflict((name,)) from error
                os.fsync(parent)
                self._fault("linked")
                staged.unlink()
            os.fsync(parent)
            self._fault("published")
            if not _same(self._files.state(name), desired):
                raise CheckpointConflict((name,))
