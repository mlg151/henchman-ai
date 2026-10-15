"""Project-local MCP authentication persistence."""

from __future__ import annotations

import json
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

        if not self._auth_path.exists():
            return {}
        raw = json.loads(self._auth_path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            return {}
        return {
            str(server): str(token)
            for server, token in raw.items()
            if str(server).strip() and str(token).strip()
        }

    def _write_payload(self, payload: dict[str, str]) -> None:
        """Persist the auth payload to disk."""

        self._auth_path.parent.mkdir(parents=True, exist_ok=True)
        self._auth_path.write_text(
            json.dumps(payload, indent=2, sort_keys=True),
            encoding="utf-8",
        )
