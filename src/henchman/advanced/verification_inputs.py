"""Bounded content fingerprints for explicitly declared verification inputs."""

from __future__ import annotations

import asyncio
import hashlib
import json
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any, TypeVar

from henchman.advanced.checkpoint_files import WorkspaceFiles
from henchman.utils.evidence_redaction import EvidenceRedactor

MAX_INPUT_FILES = 256
MAX_INPUT_BYTES = 16 * 1024 * 1024
MAX_INPUT_FILE_BYTES = 1024 * 1024
MAX_CAPTURE_SECONDS = 5.0
_T = TypeVar("_T")


def fingerprint_identity(snapshot: dict[str, Any]) -> dict[str, Any]:
    """Retain a bounded observation binding without duplicating the file map."""
    return {key: snapshot[key] for key in ("status", "digest", "reason") if key in snapshot}


def capture_inputs(root: Path, paths: tuple[str, ...], stop: threading.Event | None = None) -> dict[str, Any]:
    """Read explicit supported files without storing contents or scanning directories.

    The existing checkpoint reader supplies no-follow and native Windows file
    handling. Unsupported, ignored or unreadable inputs cannot prove freshness.
    """
    if not paths or len(paths) > MAX_INPUT_FILES:
        return {"status": "unavailable", "reason": "Verification needs 1..256 explicit input files"}
    try:
        deadline = time.monotonic() + MAX_CAPTURE_SECONDS
        workspace = WorkspaceFiles(root, EvidenceRedactor(), MAX_INPUT_FILE_BYTES, ())
        files: dict[str, Any] = {}
        consumed = 0
        for path in paths:
            if time.monotonic() >= deadline or (stop is not None and stop.is_set()):
                return {"status": "unavailable", "reason": "Verification input capture was interrupted or exceeded its deadline"}
            state = workspace.state(path)
            if time.monotonic() >= deadline or (stop is not None and stop.is_set()):
                return {"status": "unavailable", "reason": "Verification input capture was interrupted or exceeded its deadline"}
            if state.status not in {"text", "missing"}:
                return {"status": "unavailable", "reason": "A declared input is unsupported, excluded or unreadable"}
            content = state.content or b""
            consumed += len(content)
            if consumed > MAX_INPUT_BYTES:
                return {"status": "unavailable", "reason": "Declared inputs exceed the 16 MiB read limit"}
            files[path] = {"status": state.status, "mode": state.mode,
                           "sha256": hashlib.sha256(content).hexdigest() if state.status == "text" else None}
        workspace.check_root()
        if time.monotonic() >= deadline or (stop is not None and stop.is_set()):
            return {"status": "unavailable", "reason": "Verification input capture was interrupted or exceeded its deadline"}
        body = {"project": list(workspace.identity), "files": files}
        digest = hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        return {"status": "available", "digest": digest, **body}
    except (OSError, ValueError, RuntimeError):
        return {"status": "unavailable", "reason": "Declared verification inputs could not be captured consistently"}


async def capture_inputs_async(root: Path, paths: tuple[str, ...]) -> dict[str, Any]:
    """Join the bounded reader before cancellation returns to its caller."""
    stop = threading.Event()
    return await read_in_worker(lambda: capture_inputs(root, paths, stop), stop)


async def read_in_worker(action: Callable[[], _T], stop: threading.Event | None = None) -> _T:
    """Join a bounded verification reader, preserving the first cancellation."""
    worker = asyncio.create_task(asyncio.to_thread(action))
    cancelled: asyncio.CancelledError | None = None
    while not worker.done():
        try:
            await asyncio.shield(worker)
        except asyncio.CancelledError as error:
            if stop is not None:
                stop.set()
            cancelled = cancelled or error
        except BaseException:
            if not worker.done():
                raise
    try:
        result = worker.result()
    except BaseException:
        if cancelled is not None:
            cancelled.add_note("Verification input reader also failed during joined cancellation")
            raise cancelled from None
        raise
    if cancelled is not None:
        raise cancelled
    return result


def input_freshness(evidence: object, *, root: Path, paths: tuple[str, ...], complete: bool, count: int) -> str:
    """Compare validated historical bindings with current declared input contents."""
    if (not complete or not isinstance(evidence, dict) or type(evidence.get("version")) is not int or evidence.get("version") != 1
        or evidence.get("paths") != list(paths) or evidence.get("complete") is not True):
        return "unverified"
    before, after = evidence.get("before"), evidence.get("after")
    if not isinstance(before, dict) or not isinstance(after, dict):
        return "unverified"
    if before.get("status") != "available" or after.get("status") != "available":
        return "unverified"
    observations = evidence.get("observations")
    if not isinstance(observations, list) or len(observations) != count or any(
        not isinstance(item, dict) or not isinstance(item.get("before"), dict) or not isinstance(item.get("after"), dict)
        for item in observations
    ):
        return "unverified"
    if any(item[phase].get("status") != "available" for item in observations for phase in ("before", "after")):
        return "unverified"
    final_identity = fingerprint_identity(after)
    if before != final_identity or any(item[phase] != final_identity for item in observations for phase in ("before", "after")):
        return "stale"
    current = capture_inputs(root, paths)
    if current.get("status") != "available":
        return "unverified"
    return "current" if current == after else "stale"
