"""Minimal cassette support for Tier 8 contract and integration tests."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class CassetteInteraction:
    """One recorded HTTP-style interaction."""

    method: str
    url: str
    request_body: dict[str, Any] | None
    response_status: int
    response_body: dict[str, Any] | None


class CassetteLibrary:
    """Persist and load named cassette recordings."""

    def __init__(self, *, base_dir: Path) -> None:
        """Initialize the cassette library.

        Args:
            base_dir: Directory used to store cassette JSON files.
        """
        self._base_dir = Path(base_dir)

    def save(self, name: str, interactions: list[CassetteInteraction]) -> Path:
        """Persist a named cassette.

        Args:
            name: Cassette name.
            interactions: Recorded interactions to persist.

        Returns:
            Path to the saved cassette file.
        """
        path = self._path_for(name)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "name": name,
            "interactions": [asdict(interaction) for interaction in interactions],
        }
        path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        return path

    def load(self, name: str) -> list[CassetteInteraction]:
        """Load a previously saved cassette.

        Args:
            name: Cassette name.

        Returns:
            Recorded interactions for the cassette.
        """
        payload = json.loads(self._path_for(name).read_text(encoding="utf-8"))
        interactions = payload.get("interactions", [])
        return [CassetteInteraction(**interaction) for interaction in interactions]

    def match(self, name: str, *, method: str, url: str) -> CassetteInteraction | None:
        """Find a recorded interaction by method and URL.

        Args:
            name: Cassette name.
            method: HTTP method to match.
            url: URL to match.

        Returns:
            Matching interaction or ``None``.
        """
        for interaction in self.load(name):
            if interaction.method == method and interaction.url == url:
                return interaction
        return None

    def _path_for(self, name: str) -> Path:
        """Return the on-disk path for a cassette name."""
        safe_name = name.replace("/", "_")
        return self._base_dir / f"{safe_name}.json"
