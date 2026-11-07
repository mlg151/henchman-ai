"""Versioned, integrity-checked session storage with cooperative writer locking.

Storage metadata is local to disk; portable session exports do not confer the
right to overwrite an existing session. Digests detect damage, not hostile edits.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
import warnings
from pathlib import Path
from typing import Any

from henchman.utils.evidence_redaction import EvidenceRedactor
from henchman.utils.file_lock import FileLock

from .session_data import Session, session_from_dict
from .session_evidence import redact_session_payload


class SessionStorageError(ValueError):
    """Session bytes cannot be safely decoded or overwritten."""


class UnsupportedSessionVersion(SessionStorageError):
    """A newer storage version must not be silently downgraded."""


def session_path(data_dir: Path, session_id: str) -> Path:
    """Restrict session IDs/prefixes to portable, literal filenames."""
    if not re.fullmatch(r"[A-Za-z0-9_-]+", session_id):
        raise ValueError("Invalid session ID; expected letters, digits, hyphens or underscores.")
    return data_dir / f"{session_id}.json"


def _digest(raw: bytes | None) -> str | None:
    return hashlib.sha256(raw).hexdigest() if raw is not None else None


def _revision(current: bytes | None, prior: bytes | None) -> str | None:
    """Track both copies so deleting a prior-only recovery also invalidates writers."""
    if current is None and prior is None:
        return None
    return _digest(json.dumps([_digest(current), _digest(prior)]).encode())


def _canonical(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, sort_keys=True, ensure_ascii=True, separators=(",", ":")).encode()


def _read(path: Path) -> bytes | None:
    try:
        return path.read_bytes()
    except FileNotFoundError:
        return None


def _decode(raw: bytes | None, session_id: str) -> Session:
    if raw is None:
        raise SessionStorageError("missing file")
    try:
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            raise SessionStorageError("expected a session object")
        if "_storage" in payload:
            storage = payload.pop("_storage")
            if not isinstance(storage, dict):
                raise SessionStorageError("invalid storage metadata")
            if type(storage.get("version")) is not int or storage["version"] != 1:
                raise UnsupportedSessionVersion(
                    "Unsupported session storage version; upgrade before loading."
                )
            if storage.get("sha256") != _digest(_canonical(payload)):
                raise SessionStorageError("integrity check failed")
        for key in ("id", "project_hash", "started", "last_updated"):
            if not isinstance(payload.get(key), str):
                raise SessionStorageError("missing or invalid session identity/timestamps")
        if payload["id"] != session_id:
            raise SessionStorageError("session identity differs from filename")
        return session_from_dict(payload)
    except SessionStorageError:
        raise
    except (ValueError, KeyError, TypeError, AttributeError, UnicodeError) as exc:
        # Do not echo arbitrary stored content in diagnostics.
        raise SessionStorageError("invalid session data") from exc


def _load_locked(path: Path) -> Session:
    current = _read(path)
    prior = _read(path.with_suffix(".json.bak"))
    try:
        session = _decode(current, path.stem)
    except UnsupportedSessionVersion:
        raise
    except SessionStorageError as exc:
        try:
            session = _decode(prior, path.stem)
        except UnsupportedSessionVersion:
            raise
        except SessionStorageError:
            raise SessionStorageError(f"No valid session copy for {path.stem}: {exc}.") from None
        session.recovery_notice = (
            f"Recovered prior session {path.stem}: current copy {exc}. "
            "Recent changes may be missing; inspect before continuing."
        )
        warnings.warn(session.recovery_notice, UserWarning, stacklevel=3)
    session._storage_token = _revision(current, prior)
    session._storage_path = str(path.resolve())
    return session


def load_session(path: Path) -> Session:
    """Read current or prior state under the same lock used by writers."""
    with FileLock(path.with_suffix(".lock")):
        session = _load_locked(path)
        _cleanup_temporary(path)
        return session


def _cleanup_temporary(path: Path) -> bool:
    """Remove only this session's abandoned save files while holding its lock."""
    abandoned = list(path.parent.glob(f".{path.name}.*.tmp"))
    for temporary in abandoned:
        temporary.unlink(missing_ok=True)
    return bool(abandoned)


def _sync_directory(directory: Path) -> None:
    """Durably commit directory entries on POSIX; Windows has no directory fsync."""
    if os.name != "nt":
        fd = os.open(directory, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)


def _replace_bytes(path: Path, raw: bytes) -> None:
    """Flush a private unique temporary file before same-directory replacement."""
    temporary: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            dir=path.parent, prefix=f".{path.name}.", suffix=".tmp", delete=False
        ) as target:
            temporary = target.name
            target.write(raw)
            target.flush()
            os.fsync(target.fileno())
        os.replace(temporary, path)
        _sync_directory(path.parent)
    finally:
        if temporary is not None:
            Path(temporary).unlink(missing_ok=True)


def persist_session(data_dir: Path, session: Session, *, timestamp: str) -> Path:
    """Compare the loaded bytes and atomically commit with one known-good backup."""
    path = session_path(data_dir, session.id)
    data_dir.mkdir(parents=True, exist_ok=True)
    with FileLock(path.with_suffix(".lock")):
        current = _read(path)
        backup = path.with_suffix(".json.bak")
        prior = _read(backup)
        same_path = session._storage_path == str(path.resolve())
        expected = session._storage_token if same_path else None
        if _revision(current, prior) != expected:
            raise SessionStorageError(
                "Session changed on disk; reload and reconcile before saving."
            )
        retained = _select_prior(current, prior, session)
        for generation in (current, prior):
            if generation is None:
                continue
            try:
                _decode(generation, session.id)
            except SessionStorageError:
                continue  # Unusable generations cannot supply trusted metadata.
            session.evidence_redactor.register_config(json.loads(generation))
        # Learn legacy marked credentials before projecting current echoes.
        # A portable import/new object must not replace a recoverable session.
        payload = session.to_dict()
        payload["last_updated"] = timestamp
        payload["_storage"] = {"version": 1, "sha256": _digest(_canonical(payload))}
        raw = json.dumps(payload, indent=2, ensure_ascii=True).encode("utf-8")
        _decode(raw, session.id)  # Validate before touching either committed copy.
        _cleanup_temporary(path)
        if retained is not None:
            safe_prior = _redact_stored_copy(retained, session.evidence_redactor)
            _decode(safe_prior, session.id)
            if safe_prior != prior:
                _replace_bytes(backup, safe_prior)
                prior = safe_prior
        _replace_bytes(path, raw)
        session.last_updated = timestamp
        session._storage_token = _revision(raw, prior)
        session._storage_path = str(path.resolve())
    return path


def _select_prior(current: bytes | None, prior: bytes | None, session: Session) -> bytes | None:
    """Choose only a validated generation, including prior-only recovery."""
    if current is not None:
        try:
            _decode(current, session.id)
        except UnsupportedSessionVersion:
            raise
        except SessionStorageError:
            if not session.recovery_notice:
                raise
        else:
            return current
    if prior is not None:
        _decode(prior, session.id)
    return prior


def _redact_stored_copy(raw: bytes, redactor: EvidenceRedactor) -> bytes:
    """Do not rotate legacy unredacted bytes into a new retained backup."""
    payload = json.loads(raw)
    safe = redact_session_payload(payload, redactor)
    if safe == payload:
        return raw
    storage = safe.pop("_storage", None)
    if storage is not None:
        safe["_storage"] = {"version": 1, "sha256": _digest(_canonical(safe))}
    return json.dumps(safe, indent=2, ensure_ascii=True).encode("utf-8")


def delete_session(path: Path) -> None:
    """Delete both generations under the writer lock, keeping its inode stable."""
    with FileLock(path.with_suffix(".lock")):
        backup = path.with_suffix(".json.bak")
        removed_temporary = _cleanup_temporary(path)
        if not path.exists() and not backup.exists() and not removed_temporary:
            raise FileNotFoundError(f"Session not found: {path.stem}")
        backup.unlink(missing_ok=True)
        path.unlink(missing_ok=True)
        _sync_directory(path.parent)


def session_paths(data_dir: Path, prefix: str = "") -> list[Path]:
    """Include recoverable prior-only sessions without exposing duplicate rows."""
    paths = set(data_dir.glob(f"{prefix}*.json"))
    paths.update(path.with_suffix("") for path in data_dir.glob(f"{prefix}*.json.bak"))
    return sorted(paths)
