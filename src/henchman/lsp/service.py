"""Generic stdio LSP service."""

from __future__ import annotations

import asyncio
import atexit
import contextlib
import json
from asyncio.subprocess import Process
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, ClassVar

from henchman.config.paths import resolve_project_settings_path


def _read_json(path: Path, *, default: object) -> object:
    """Read one JSON payload or return *default* when absent."""

    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: object) -> None:
    """Persist one JSON payload with stable formatting."""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


@dataclass(frozen=True, slots=True)
class LspServerRecord:
    """Persisted LSP server configuration."""

    server: str
    command: str
    args: tuple[str, ...]
    language: str | None
    root_uri: str
    running: bool

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-serializable representation."""

        return {
            "server": self.server,
            "command": self.command,
            "args": list(self.args),
            "language": self.language,
            "root_uri": self.root_uri,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> LspServerRecord:
        """Create a server record from persisted data."""

        raw_args = payload.get("args", [])
        args = tuple(str(item).strip() for item in raw_args if str(item).strip()) if isinstance(raw_args, list) else ()
        return cls(
            server=str(payload.get("server", "")),
            command=str(payload.get("command", "")),
            args=args,
            language=str(payload["language"]) if payload.get("language") is not None else None,
            root_uri=str(payload.get("root_uri", "")),
            running=False,
        )


@dataclass(slots=True)
class _LspSession:
    """In-memory LSP subprocess session."""

    process: Process
    next_id: int = 0


@dataclass(slots=True)
class _LspRuntime:
    """Shared in-memory runtime for one project root."""

    sessions: dict[str, _LspSession]


class LspService:
    """Manage project-local generic stdio language servers."""

    _runtimes: ClassVar[dict[Path, _LspRuntime]] = {}
    _atexit_registered: ClassVar[bool] = False

    def __init__(self, project_root: Path | None = None) -> None:
        """Initialize the LSP service for one project root."""

        self._project_root = (project_root or Path.cwd()).resolve()
        self._storage_dir = resolve_project_settings_path(self._project_root) / "lsp"
        self._index_path = self._storage_dir / "servers.json"
        self._runtime = self._runtimes.setdefault(self._storage_dir, _LspRuntime(sessions={}))

        # Register class-level atexit cleanup once per process
        if not LspService._atexit_registered:
            LspService._atexit_registered = True
            atexit.register(LspService.cleanup_all)

    def register_server(
        self,
        *,
        server: str,
        command: str,
        args: list[str] | tuple[str, ...] | None = None,
        language: str | None = None,
        root_uri: str | None = None,
    ) -> LspServerRecord:
        """Persist one LSP server configuration."""

        if not server.strip() or not command.strip():
            msg = "Both server and command are required."
            raise ValueError(msg)
        records = self._load_records()
        records[server] = LspServerRecord(
            server=server.strip(),
            command=command.strip(),
            args=tuple(str(item).strip() for item in (args or []) if str(item).strip()),
            language=language.strip() if isinstance(language, str) and language.strip() else None,
            root_uri=root_uri.strip() if isinstance(root_uri, str) and root_uri.strip() else self._project_root.as_uri(),
            running=server in self._runtime.sessions,
        )
        self._persist_records(records)
        return records[server]

    def list_servers(self) -> list[LspServerRecord]:
        """Return all configured LSP servers."""

        records = self._load_records()
        return sorted(
            (
                replace(record, running=record.server in self._runtime.sessions)
                for record in records.values()
            ),
            key=lambda record: record.server,
        )

    async def start_server(self, server: str) -> LspServerRecord:
        """Start one configured LSP server."""

        records = self._load_records()
        record = records.get(server)
        if record is None:
            msg = f"LSP server {server} not found."
            raise KeyError(msg)
        if server in self._runtime.sessions:
            return replace(record, running=True)

        process = await asyncio.create_subprocess_exec(
            record.command,
            *record.args,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        self._runtime.sessions[server] = _LspSession(process=process)
        await self.request(
            server,
            "initialize",
            {
                "processId": None,
                "rootUri": record.root_uri,
                "capabilities": {},
            },
        )
        await self.notify(server, "initialized", {})
        return replace(record, running=True)

    async def stop_server(self, server: str) -> LspServerRecord | None:
        """Stop one running LSP server."""

        records = self._load_records()
        record = records.get(server)
        if record is None:
            return None
        session = self._runtime.sessions.get(server)
        if session is not None:
            with contextlib.suppress(Exception):
                await self.request(server, "shutdown", {})
            await self.notify(server, "exit", {})
            if session.process.returncode is None:
                session.process.terminate()
                await session.process.wait()
            self._runtime.sessions.pop(server, None)
        return replace(record, running=False)

    async def stop_all(self) -> None:
        """Terminate all running LSP servers for this runtime.

        Iterates over a snapshot of the session keys and calls
        *stop_server* for each one, discarding errors so all
        servers get a shutdown attempt.
        """
        for server in list(self._runtime.sessions):
            with contextlib.suppress(Exception):
                await self.stop_server(server)

    @classmethod
    def cleanup_all(cls) -> None:
        """Terminate ALL LSP subprocesses across every runtime.

        This is a synchronous best-effort cleanup: running processes
        receive SIGTERM via ``process.terminate()``.  Already-exited
        processes are skipped.  All runtime state is cleared afterward.

        Intended for ``atexit`` registration (set up automatically on
        first ``LspService`` construction) and for explicit shutdown
        callers such as unit tests.
        """
        for runtime in cls._runtimes.values():
            for session in runtime.sessions.values():
                if session.process.returncode is None:
                    with contextlib.suppress(Exception):
                        session.process.terminate()
            runtime.sessions.clear()
        cls._runtimes.clear()

    def __del__(self) -> None:
        """Safety net: terminate orphaned subprocesses on GC.

        Only terminates processes that belong to *this* instance's
        runtime.  The class-level :meth:`cleanup_all` handles the
        (rare) case where the whole class dict outlives individual
        instances.
        """
        runtime = getattr(self, "_runtime", None)
        if runtime is not None:
            for session in list(runtime.sessions.values()):
                if session.process.returncode is None:
                    with contextlib.suppress(Exception):
                        session.process.terminate()

    async def notify(self, server: str, method: str, params: dict[str, object]) -> None:
        """Send one LSP notification to a running server."""

        session = self._require_session(server)
        await self._write_message(
            session.process,
            {"jsonrpc": "2.0", "method": method, "params": params},
        )

    async def request(self, server: str, method: str, params: dict[str, object]) -> object:
        """Send one LSP request and return the response result."""

        session = self._require_session(server)
        message_id = session.next_id
        session.next_id += 1
        await self._write_message(
            session.process,
            {"jsonrpc": "2.0", "id": message_id, "method": method, "params": params},
        )
        while True:
            response = await self._read_message(session.process)
            if response.get("id") != message_id:
                continue
            if "error" in response:
                msg = json.dumps(response["error"], sort_keys=True)
                raise ValueError(msg)
            return response.get("result")

    def _require_session(self, server: str) -> _LspSession:
        """Return one running session or raise when absent."""

        session = self._runtime.sessions.get(server)
        if session is None:
            msg = f"LSP server {server} is not running."
            raise KeyError(msg)
        return session

    def _load_records(self) -> dict[str, LspServerRecord]:
        """Load configured LSP servers from disk."""

        payload = _read_json(self._index_path, default=[])
        if not isinstance(payload, list):
            return {}
        records: dict[str, LspServerRecord] = {}
        for item in payload:
            if not isinstance(item, dict):
                continue
            record = LspServerRecord.from_dict(item)
            records[record.server] = record
        return records

    def _persist_records(self, records: dict[str, LspServerRecord]) -> None:
        """Persist configured LSP servers to project-local storage."""

        payload = [record.to_dict() for record in sorted(records.values(), key=lambda item: item.server)]
        _write_json(self._index_path, payload)

    async def _write_message(self, process: Process, payload: dict[str, Any]) -> None:
        """Write one JSON-RPC message to the server process."""

        writer = process.stdin
        if writer is None:
            msg = "LSP server stdin is unavailable."
            raise RuntimeError(msg)
        body = json.dumps(payload).encode("utf-8")
        writer.write(f"Content-Length: {len(body)}\r\n\r\n".encode())
        writer.write(body)
        await writer.drain()

    async def _read_message(self, process: Process) -> dict[str, Any]:
        """Read one JSON-RPC message from the server process."""

        reader = process.stdout
        if reader is None:
            msg = "LSP server stdout is unavailable."
            raise RuntimeError(msg)

        headers: dict[str, str] = {}
        while True:
            line = await reader.readline()
            if not line:
                msg = "LSP server closed the connection."
                raise RuntimeError(msg)
            if line in {b"\r\n", b"\n"}:
                break
            name, value = line.decode("utf-8").split(":", 1)
            headers[name.strip().lower()] = value.strip()

        content_length = int(headers.get("content-length", "0"))
        body = await reader.readexactly(content_length)
        payload = json.loads(body.decode("utf-8"))
        if not isinstance(payload, dict):
            msg = "LSP responses must be JSON objects."
            raise RuntimeError(msg)
        return payload
