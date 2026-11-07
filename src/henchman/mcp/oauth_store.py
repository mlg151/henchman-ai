"""Private bounded OAuth records with persistent revocation and refresh authority."""

from __future__ import annotations

import hashlib
import math
import os
import stat
import tempfile
import time
import uuid
from collections.abc import Callable, Iterator
from contextlib import contextmanager, suppress
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal
from weakref import WeakSet

from pydantic import BaseModel, ConfigDict, Field, model_validator

from henchman.config.paths import resolve_project_settings_path
from henchman.mcp.oauth import OAuthBinding, OAuthError, bounded_oauth_json
from henchman.utils.evidence_redaction import EvidenceRedactor
from henchman.utils.file_lock import _set_file_lock

MAX_OAUTH_STORE_BYTES = 1024 * 1024
MAX_OAUTH_RECORDS = 128
_State = Literal["empty", "revoked", "ready", "login_started", "refresh_started", "needs_login"]


class OAuthStoreError(OAuthError):
    """Value-free credential persistence or authority error."""


class OAuthCredentials(BaseModel):
    """Validated raw credentials; intentionally absent from repr and status evidence."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, hide_input_in_errors=True)

    access_token: str = Field(min_length=1, max_length=8192, repr=False)
    refresh_token: str | None = Field(default=None, min_length=1, max_length=8192, repr=False)
    token_endpoint: str = Field(min_length=1, max_length=4096, repr=False)
    scopes: tuple[str, ...] = Field(default=(), max_length=128, repr=False)
    issued_at: float = Field(ge=0, allow_inf_nan=False, repr=False)
    expires_at: float | None = Field(default=None, ge=0, allow_inf_nan=False, repr=False)

    @model_validator(mode="after")
    def validate_values(self) -> OAuthCredentials:
        from henchman.config.mcp import validate_oauth_url
        from henchman.mcp.oauth import _scopes

        validate_oauth_url(self.token_endpoint, allow_query=True)
        _scopes(list(self.scopes))
        if any(not 33 <= ord(char) <= 126 for token in (self.access_token, self.refresh_token or "") for char in token):
            raise ValueError("OAuth credentials contain unsupported characters")
        if self.expires_at is not None and self.expires_at < self.issued_at:
            raise ValueError("OAuth credential expiry predates issuance")
        return self


class _Record(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, hide_input_in_errors=True)

    fingerprint: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    generation: int = Field(ge=1)
    state: _State
    claim_id: str | None = Field(default=None, pattern=r"^[a-f0-9]{32}$")
    credentials: OAuthCredentials | None = None

    @model_validator(mode="after")
    def validate_state(self) -> _Record:
        if (self.state == "ready") != (self.credentials is not None):
            raise ValueError("Invalid OAuth credential state")
        if (self.state in {"login_started", "refresh_started"}) != (self.claim_id is not None):
            raise ValueError("Invalid OAuth claim state")
        if self.fingerprint is None and self.state != "revoked":
            raise ValueError("Invalid OAuth unbound state")
        return self


class _Payload(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, hide_input_in_errors=True)

    version: Literal[1] = 1
    store_id: str = Field(pattern=r"^[a-f0-9]{32}$")
    project_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    records: dict[str, _Record] = Field(default_factory=dict, max_length=MAX_OAUTH_RECORDS)


@dataclass(frozen=True, repr=False)
class OAuthAuthority:
    store_id: str
    binding: OAuthBinding
    generation: int


@dataclass(frozen=True, repr=False)
class OAuthClaim:
    authority: OAuthAuthority
    claim_id: str
    kind: Literal["login", "refresh"]
    refresh_token: str | None = field(default=None, repr=False)
    previous_scopes: tuple[str, ...] = ()
    token_endpoint: str | None = None


@dataclass(frozen=True)
class OAuthStatus:
    """Credential-free status; no opaque source strings or token values."""

    state: str
    generation: int
    expires_at: float | None = None
    refresh_available: bool = False


class OAuthCredentialStore:
    """Keep server tombstones and generation claims independently of legacy stdio auth."""

    def __init__(self, project_root: Path, *, clock: Callable[[], float] = time.time) -> None:
        self._root = project_root.resolve()
        self._directory = resolve_project_settings_path(self._root) / "mcp"
        self._path = self._directory / "oauth.json"
        self._project_hash = hashlib.sha256(os.fsencode(self._root)).hexdigest()
        self._clock = clock
        self._evidence = EvidenceRedactor()
        self._evidence_policies: WeakSet[EvidenceRedactor] = WeakSet()

    def register_evidence(self, policy: EvidenceRedactor) -> None:
        """Bind evidence before any read or mutation, retaining earlier learned credentials."""
        self._evidence_policies.add(policy)
        policy.register_policy(self._evidence)
        self._read()

    def remember_evidence(self, payload: object) -> None:
        """Learn bounded credential-bearing input before validation or replacement."""
        self._evidence.register_config(payload)
        for policy in self._evidence_policies:
            policy.register_policy(self._evidence)

    def _check_directories(self, *, create: bool = False) -> bool:
        for directory in (self._directory.parent, self._directory):
            try:
                metadata = directory.lstat()
            except FileNotFoundError:
                if not create:
                    return False
                with suppress(FileExistsError):
                    directory.mkdir(mode=0o700)
                metadata = directory.lstat()
            if not stat.S_ISDIR(metadata.st_mode) or self._reparse(metadata):
                raise OAuthStoreError("OAuth storage directory must not be a symlink or reparse point")
        return True

    @staticmethod
    def _reparse(metadata: os.stat_result) -> bool:
        return bool(getattr(metadata, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0))

    @contextmanager
    def _directory_handle(self, *, create: bool = False) -> Iterator[int | None]:
        """Pin POSIX parent directories; Windows rejects existing reparse points."""
        if os.name != "posix":
            if not self._check_directories(create=create):
                raise FileNotFoundError
            yield None
            return
        descriptor = os.open(self._root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            for name in (".henchman", "mcp"):
                if create:
                    with suppress(FileExistsError):
                        os.mkdir(name, 0o700, dir_fd=descriptor)
                child = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=descriptor)
                os.close(descriptor)
                descriptor = child
            yield descriptor
        finally:
            os.close(descriptor)

    def _open(self, path: Path, *, create: bool = False, directory_fd: int | None = None) -> int:
        location = path.name if directory_fd is not None else path
        try:
            before = os.stat(location, dir_fd=directory_fd, follow_symlinks=False)
        except FileNotFoundError:
            before = None
        if before is not None and (not stat.S_ISREG(before.st_mode) or self._reparse(before)):
            raise OAuthStoreError("OAuth storage must be a regular file")
        flags = (os.O_RDWR | os.O_CREAT) if create else os.O_RDONLY
        descriptor = os.open(location, flags | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0),
                             0o600, dir_fd=directory_fd)
        try:
            opened = os.fstat(descriptor)
            current = os.stat(location, dir_fd=directory_fd, follow_symlinks=False)
            if (not stat.S_ISREG(opened.st_mode) or self._reparse(current)
                or (opened.st_dev, opened.st_ino) != (current.st_dev, current.st_ino)
                or (before is not None and (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino))):
                raise OAuthStoreError("OAuth storage changed while opening")
            return descriptor
        except BaseException:
            os.close(descriptor)
            raise

    @contextmanager
    def _locked(self) -> Iterator[int | None]:
        """Take a native nonblocking lock; credential operations never wait on another process."""
        try:
            with self._directory_handle(create=True) as directory_fd:
                descriptor = self._open(self._directory / "oauth.lock", create=True, directory_fd=directory_fd)
                with os.fdopen(descriptor, "r+b") as handle:
                    _set_file_lock(handle)
                    try:
                        yield directory_fd
                    finally:
                        _set_file_lock(handle, unlock=True)
        except OAuthStoreError:
            raise
        except (OSError, ValueError, TypeError, OAuthError):
            raise OAuthStoreError("OAuth storage is unavailable, busy or invalid") from None

    @staticmethod
    def _server(server: str) -> None:
        if not isinstance(server, str) or not server or len(server) > 256 or any(ord(char) < 32 for char in server):
            raise OAuthStoreError("OAuth server identity is invalid")

    def _read(self) -> _Payload | None:
        try:
            with self._directory_handle() as directory_fd:
                return self._read_from(directory_fd)
        except FileNotFoundError:
            return None
        except OAuthStoreError:
            raise
        except OSError:
            raise OAuthStoreError("OAuth storage is unavailable or invalid; original data retained") from None

    def _read_from(self, directory_fd: int | None) -> _Payload | None:
        try:
            if directory_fd is None and not self._check_directories():
                return None
            try:
                descriptor = self._open(self._path, directory_fd=directory_fd)
            except FileNotFoundError:
                return None
            with os.fdopen(descriptor, "rb") as handle:
                raw = handle.read(MAX_OAUTH_STORE_BYTES + 1)
            data = bounded_oauth_json(raw, limit=MAX_OAUTH_STORE_BYTES)
            self.remember_evidence(data)
            if type(data.get("version")) is not int:
                raise ValueError
            # JSON arrays encode the immutable scope tuple; all other fields stay strict.
            for record in data.get("records", {}).values():
                if isinstance(record, dict) and isinstance(record.get("credentials"), dict):
                    credentials = record["credentials"]
                    if isinstance(credentials.get("scopes"), list):
                        credentials["scopes"] = tuple(credentials["scopes"])
            payload = _Payload.model_validate(data)
            if payload.project_hash != self._project_hash:
                raise ValueError
            for server in payload.records:
                self._server(server)
            return payload
        except OAuthStoreError:
            raise
        except (OSError, ValueError, TypeError, AttributeError, OAuthError):
            raise OAuthStoreError("OAuth storage is unavailable or invalid; original data retained") from None

    def _write(self, payload: _Payload, directory_fd: int | None) -> None:
        raw = payload.model_dump_json().encode("utf-8")
        if len(raw) > MAX_OAUTH_STORE_BYTES or len(payload.records) > MAX_OAUTH_RECORDS:
            raise OAuthStoreError("OAuth storage exceeds its bound; tombstones cannot be evicted")
        bounded_oauth_json(raw, limit=MAX_OAUTH_STORE_BYTES)
        if directory_fd is None:
            self._check_directories()
        # Recheck the destination even on a first write, refusing an injected symlink.
        try:
            descriptor = self._open(self._path, directory_fd=directory_fd)
        except FileNotFoundError:
            pass
        else:
            os.close(descriptor)
        if directory_fd is None:
            descriptor, temporary = tempfile.mkstemp(prefix=".oauth-", suffix=".tmp", dir=self._directory)
        else:
            temporary = f".oauth-{uuid.uuid4().hex}.tmp"
            descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                                 0o600, dir_fd=directory_fd)
        try:
            with os.fdopen(descriptor, "wb") as handle:
                if handle.write(raw) != len(raw):
                    raise OSError
                handle.flush()
                os.fsync(handle.fileno())
            if directory_fd is None:
                self._check_directories()
                os.replace(temporary, self._path)
            else:
                os.replace(temporary, self._path.name, src_dir_fd=directory_fd, dst_dir_fd=directory_fd)
                os.fsync(directory_fd)
        finally:
            with suppress(FileNotFoundError):
                os.unlink(temporary, dir_fd=directory_fd)

    def _payload(self, directory_fd: int | None) -> _Payload:
        return self._read_from(directory_fd) or _Payload(store_id=uuid.uuid4().hex, project_hash=self._project_hash)

    @staticmethod
    def _authority(payload: _Payload, binding: OAuthBinding) -> OAuthAuthority:
        return OAuthAuthority(payload.store_id, binding, payload.records[binding.server].generation)

    def _require(self, payload: _Payload, authority: OAuthAuthority) -> _Record:
        record = payload.records.get(authority.binding.server)
        if (payload.store_id != authority.store_id or record is None
            or record.generation != authority.generation or record.fingerprint != authority.binding.fingerprint):
            raise OAuthStoreError("OAuth authority is stale; inspect current state before retrying")
        if record.credentials is not None:
            try:
                authority.binding.check_destination(record.credentials.token_endpoint)
            except OAuthError:
                raise OAuthStoreError("OAuth stored credential destination is not authorized") from None
        return record

    def bind(self, binding: OAuthBinding) -> OAuthAuthority:
        """Publish a configuration binding, revoking any previous configuration's claims."""
        self._server(binding.server)
        with self._locked() as directory_fd:
            payload = self._payload(directory_fd)
            record = payload.records.get(binding.server)
            if record is None or record.fingerprint != binding.fingerprint:
                payload.records[binding.server] = _Record(fingerprint=binding.fingerprint,
                                                          generation=record.generation + 1 if record else 1, state="empty")
                self._write(payload, directory_fd)
            return self._authority(payload, binding)

    def status(self, server: str) -> OAuthStatus:
        """Read credential-free state without creating files or recovering pending claims."""
        self._server(server)
        payload = self._read()
        record = payload.records.get(server) if payload else None
        if record is None:
            return OAuthStatus("missing", 0)
        credentials = record.credentials
        return OAuthStatus(record.state, record.generation, credentials.expires_at if credentials else None,
                           bool(credentials and credentials.refresh_token))

    def bound_status(self, binding: OAuthBinding) -> tuple[OAuthStatus, OAuthAuthority | None]:
        """Inspect one configuration from one read without rebinding or releasing tokens."""
        self._server(binding.server)
        payload = self._read()
        record = payload.records.get(binding.server) if payload else None
        if record is None or payload is None:
            return OAuthStatus("missing", 0), None
        if record.fingerprint != binding.fingerprint:
            return OAuthStatus("configuration_changed", record.generation), None
        authority = self._authority(payload, binding)
        self._require(payload, authority)
        credentials = record.credentials
        return (OAuthStatus(record.state, record.generation, credentials.expires_at if credentials else None,
                            bool(credentials and credentials.refresh_token)), authority)

    def credentials(self, authority: OAuthAuthority) -> OAuthCredentials | None:
        """Return a detached ready token only while its exact bound authority remains valid."""
        payload = self._read()
        if payload is None:
            raise OAuthStoreError("OAuth authority storage is missing")
        credentials = self._require(payload, authority).credentials
        if credentials is not None:
            now = self._clock()
            if (not math.isfinite(now) or now < credentials.issued_at
                or (credentials.expires_at is not None and now >= credentials.expires_at)):
                return None
        return credentials.model_copy(deep=True) if credentials is not None else None

    def check_authority(self, authority: OAuthAuthority) -> None:
        """Check a captured configuration generation without returning credential values."""
        payload = self._read()
        if payload is None:
            raise OAuthStoreError("OAuth authority storage is missing")
        self._require(payload, authority)

    def _begin(self, authority: OAuthAuthority, kind: Literal["login", "refresh"]) -> OAuthClaim:
        with self._locked() as directory_fd:
            payload = self._payload(directory_fd)
            record = self._require(payload, authority)
            if record.state in {"login_started", "refresh_started"}:
                raise OAuthStoreError("OAuth operation is already pending; explicit logout is required to abandon it")
            previous = record.credentials
            if kind == "refresh" and (previous is None or previous.refresh_token is None):
                raise OAuthStoreError("OAuth refresh credentials are unavailable; login is required")
            claim_id = uuid.uuid4().hex
            payload.records[authority.binding.server] = _Record(
                fingerprint=record.fingerprint, generation=record.generation + 1,
                state="login_started" if kind == "login" else "refresh_started", claim_id=claim_id,
            )
            self._write(payload, directory_fd)
            # The old rotating refresh token leaves the store only after the claim is persisted.
            return OAuthClaim(self._authority(payload, authority.binding), claim_id, kind,
                              previous.refresh_token if kind == "refresh" and previous else None,
                              previous.scopes if previous else (),
                              previous.token_endpoint if kind == "refresh" and previous else None)

    def begin_login(self, authority: OAuthAuthority) -> OAuthClaim:
        return self._begin(authority, "login")

    def begin_refresh(self, authority: OAuthAuthority) -> OAuthClaim:
        return self._begin(authority, "refresh")

    def _require_claim(self, payload: _Payload, claim: OAuthClaim) -> _Record:
        record = self._require(payload, claim.authority)
        if record.claim_id != claim.claim_id or record.state != f"{claim.kind}_started":
            raise OAuthStoreError("OAuth operation claim is stale")
        return record

    def check_claim(self, claim: OAuthClaim) -> None:
        """Recheck a pending claim immediately before a future token exchange or refresh."""
        payload = self._read()
        if payload is None:
            raise OAuthStoreError("OAuth authority storage is missing")
        self._require_claim(payload, claim)

    def complete(self, claim: OAuthClaim, credentials: OAuthCredentials) -> OAuthAuthority:
        """Commit once; logout, config changes and other completions invalidate old claims."""
        self.remember_evidence(credentials.model_dump())
        try:
            credentials = OAuthCredentials.model_validate(credentials.model_dump())
            claim.authority.binding.check_destination(credentials.token_endpoint)
        except (ValueError, OAuthError):
            raise OAuthStoreError("OAuth credential response is invalid for its authority") from None
        with self._locked() as directory_fd:
            payload = self._payload(directory_fd)
            record = self._require_claim(payload, claim)
            payload.records[claim.authority.binding.server] = _Record(
                fingerprint=record.fingerprint, generation=record.generation + 1, state="ready", credentials=credentials,
            )
            self._write(payload, directory_fd)
            return self._authority(payload, claim.authority.binding)

    def abandon(self, claim: OAuthClaim) -> None:
        """Mark an owned failed operation unusable without replaying or restoring old tokens."""
        with self._locked() as directory_fd:
            payload = self._payload(directory_fd)
            record = self._require_claim(payload, claim)
            payload.records[claim.authority.binding.server] = _Record(
                fingerprint=record.fingerprint, generation=record.generation + 1, state="needs_login",
            )
            self._write(payload, directory_fd)

    def logout(self, server: str) -> None:
        """Persist a tombstone even when no token exists; never recycle a generation."""
        self._server(server)
        with self._locked() as directory_fd:
            payload = self._payload(directory_fd)
            record = payload.records.get(server)
            payload.records[server] = _Record(fingerprint=record.fingerprint if record else None,
                                              generation=record.generation + 1 if record else 1, state="revoked")
            self._write(payload, directory_fd)
