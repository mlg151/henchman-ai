"""Strict persisted checkpoint shapes; malformed authority is never a restore plan."""

from __future__ import annotations

import math
import re
from pathlib import PurePosixPath
from typing import Any

from henchman.advanced.checkpoint_models import FileState


def identifier(value: Any) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[a-f0-9]{32}", value) is not None


def _path(value: Any) -> bool:
    if not isinstance(value, str) or not value or len(value) > 4096 or "\x00" in value or "\\" in value:
        return False
    path = PurePosixPath(value)
    return not path.is_absolute() and ".." not in path.parts and path.as_posix() == value and value != "."


def _mapping(value: Any) -> bool:
    return isinstance(value, dict) and 0 < len(value) <= 256 and all(_path(path) for path in value)


def validate(payload: dict[str, Any], identity: str, *, plan: bool, max_file_bytes: int) -> None:
    """Validate complete record fields before exposing or acting on stored data."""
    common = {"version", "id", "project", "repository", "revision"}
    required = common | ({"checkpoint", "decision", "state", "changes", "applied", "changed", "hunks", "created"} if plan
                         else {"actor", "created", "state", "before", "after", "decisions", "accepted_hunks"})
    allowed = required if plan else required | {"last_plan"}
    if not required <= payload.keys() or not payload.keys() <= allowed:
        raise ValueError("Invalid checkpoint record fields")
    if type(payload["version"]) is not int or payload["version"] != 1 or payload["id"] != identity or not identifier(identity):
        raise ValueError("Checkpoint filename and record identity disagree")
    project = payload["project"]
    if not isinstance(project, (list, tuple)) or len(project) != 2 or any(type(item) is not int or item < 0 for item in project):
        raise ValueError("Invalid checkpoint project identity")
    repository = payload["repository"]
    if repository is not None and (not isinstance(repository, str) or not re.fullmatch(r"[a-f0-9]{64}", repository)):
        raise ValueError("Invalid checkpoint repository identity")
    if type(payload["revision"]) is not int or payload["revision"] < 0:
        raise ValueError("Invalid checkpoint revision")
    created = payload["created"]
    if type(created) not in {int, float} or not math.isfinite(created) or created < 0:
        raise ValueError("Invalid checkpoint timestamp")

    def file(value: Any) -> FileState:
        result = FileState.from_dict(value)
        if result.content is not None and len(result.content) > max_file_bytes:
            raise ValueError("Checkpoint content exceeds current size policy")
        return result

    if not plan:
        if payload["state"] not in {"capturing", "ready"} or not isinstance(payload["actor"], str) or len(payload["actor"]) > 4096:
            raise ValueError("Invalid checkpoint state or actor")
        before, after = payload["before"], payload["after"]
        if not _mapping(before) or not isinstance(after, dict):
            raise ValueError("Invalid checkpoint scope")
        if payload["state"] == "capturing":
            if after or payload["revision"] != 0:
                raise ValueError("Incomplete capture has invalid after state")
        elif before.keys() != after.keys() or payload["revision"] < 1:
            raise ValueError("Before/after checkpoint scopes disagree")
        for value in (*before.values(), *after.values()):
            file(value)
        decisions = payload["decisions"]
        accepted = payload["accepted_hunks"]
        if not isinstance(decisions, dict) or not decisions.keys() <= before.keys() or any(
            decision not in {"accept", "reject", "partial"} for decision in decisions.values()
        ):
            raise ValueError("Invalid checkpoint decisions")
        if not isinstance(accepted, dict) or not accepted.keys() <= before.keys() or any(
            not isinstance(values, list) or len(values) != len(set(values)) or any(
                not isinstance(value, str) or not re.fullmatch(r"[a-f0-9]{64}", value) for value in values
            ) for values in accepted.values()
        ):
            raise ValueError("Invalid accepted hunk identities")
        if "last_plan" in payload and not identifier(payload["last_plan"]):
            raise ValueError("Invalid previous decision identity")
        return
    if not identifier(payload["checkpoint"]) or payload["state"] not in {"preview", "prepared", "done"}:
        raise ValueError("Invalid restore plan state")
    if payload["decision"] not in {"accept", "reject"} or payload["revision"] < 1 or not _mapping(payload["changes"]):
        raise ValueError("Invalid restore decision")
    changes = payload["changes"]
    for change in changes.values():
        if not isinstance(change, dict) or set(change) != {"expected", "desired"}:
            raise ValueError("Invalid restore change fields")
        expected, desired = file(change["expected"]), file(change["desired"])
        if not expected.restorable or not desired.restorable or expected.parents != desired.parents:
            raise ValueError("Unsupported restore file state")
        if payload["decision"] == "accept" and expected != desired:
            raise ValueError("Accept decisions must not modify content")
    applied, changed = payload["applied"], payload["changed"]
    if not isinstance(applied, list) or applied != sorted(changes)[:len(applied)]:
        raise ValueError("Invalid restore progress")
    expected_changed = [path for path in applied if changes[path]["expected"] != changes[path]["desired"]]
    if changed != expected_changed or payload["state"] == "preview" and applied:
        raise ValueError("Invalid changed-file progress")
    if payload["state"] == "done" and set(applied) != changes.keys():
        raise ValueError("Completed restore has unapplied files")
    hunks = payload["hunks"]
    if hunks is not None and (not isinstance(hunks, dict) or hunks.keys() != changes.keys() or any(
        not isinstance(indices, list) or not indices or any(type(index) is not int or index < 0 for index in indices)
        or len(indices) != len(set(indices)) for indices in hunks.values()
    )):
        raise ValueError("Invalid selected hunk indices")
