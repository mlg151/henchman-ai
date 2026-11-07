"""Project-local MCP authentication persistence."""

from __future__ import annotations

import json
import os
import stat
import tempfile
from pathlib import Path

from henchman.config.paths import resolve_project_settings_path


class McpAuthService:
    """Persist lightweight auth tokens for configured MCP servers."""

    def __init__(self, project_root: Path | None = None) -> None:
        """Initialize the auth service for one project root."""

        self._project_root = (project_root or Path.cwd()).resolve()
        self._storage_dir = resolve_project_settings_path(self._project_root) / "mcp"
        self._auth_path = self._storage_dir / "auth.json"

    def set_token(self, server: str, token: str) -> None:
        """Persist or replace a token for one MCP server."""

        payload = self._read_payload()
        payload[server] = token
        self._write_payload(payload)

    def clear_token(self, server: str) -> bool:
        """Remove one persisted token and return whether it existed."""

        payload = self._read_payload()
        if server not in payload:
            return False
        del payload[server]
        self._write_payload(payload)
        return True

    def get_token(self, server: str) -> str | None:
        """Return one persisted token when present."""

        return self._read_payload().get(server)

    def has_token(self, server: str) -> bool:
        """Return whether a token exists for one MCP server."""

        return server in self._read_payload()

    def list_statuses(self) -> dict[str, bool]:
        """Return a mapping of server name to auth presence."""

        return dict.fromkeys(self._read_payload(), True)

    def _read_payload(self) -> dict[str, str]:
        """Read the auth payload from disk."""

        try:
            metadata = self._auth_path.lstat()
        except FileNotFoundError:
            return {}
        if not stat.S_ISREG(metadata.st_mode):
            raise OSError("MCP auth storage must be a regular file, not a symlink")
        descriptor = os.open(
            self._auth_path,
            os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0),
        )
        with os.fdopen(descriptor, "r", encoding="utf-8") as handle:
            opened = os.fstat(handle.fileno())
            if not stat.S_ISREG(opened.st_mode):
                raise OSError("MCP auth storage must be a regular file")
            if (opened.st_dev, opened.st_ino) != (metadata.st_dev, metadata.st_ino):
                raise OSError("MCP auth storage changed while opening; retry the operation")
            raw = json.load(handle)
        if not isinstance(raw, dict):
            return {}
        return {
            str(server): str(token)
            for server, token in raw.items()
            if str(server).strip() and str(token).strip()
        }

    def _write_payload(self, payload: dict[str, str]) -> None:
        """Persist the auth payload to disk."""

        self._auth_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        descriptor, temporary = tempfile.mkstemp(prefix=".auth-", suffix=".tmp", dir=self._auth_path.parent)
        try:
            # mkstemp creates mode 0600 on POSIX. Do not preserve a legacy
            # destination's public mode. Windows permissions follow its ACL.
            try:
                with os.fdopen(descriptor, "w", encoding="utf-8", closefd=False) as handle:
                    json.dump(payload, handle, indent=2, sort_keys=True)
                    handle.flush()
                    os.fsync(descriptor)
            finally:
                os.close(descriptor)
            os.replace(temporary, self._auth_path)
        finally:
            Path(temporary).unlink(missing_ok=True)
