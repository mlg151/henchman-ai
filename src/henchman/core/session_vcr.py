"""Simple VCR/playback support for persisted sessions."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .session_data import Session


class SessionVcrService:
    """Persist and load session playback recordings."""

    def __init__(self, base_dir: Path | None = None) -> None:
        """Initialize the VCR service with an optional storage directory."""

        self._base_dir = base_dir or (Path.home() / ".henchman" / "vcr")

    def build_playback(self, session: Session) -> dict[str, Any]:
        """Build a JSON-serializable playback payload for one session."""

        events: list[dict[str, Any]] = []
        for index, message in enumerate(session.messages):
            events.append(
                {
                    "type": "message",
                    "index": index,
                    "role": message.role,
                    "content": message.content,
                    "tool_call_id": message.tool_call_id,
                    "tool_calls": message.tool_calls or [],
                    "agent_id": message.agent_id,
                },
            )
        for index, summary in enumerate(session.turn_summaries):
            if summary.summary_text:
                events.append(
                    {
                        "type": "summary",
                        "index": index,
                        "summary": summary.summary_text,
                    },
                )

        return {
            "session_id": session.id,
            "tag": session.tag,
            "events": events,
        }

    def record_session(self, session: Session, destination: Path | None = None) -> Path:
        """Persist a playback recording for one session."""

        path = destination or (self._base_dir / f"{session.id}.json")
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = self.build_playback(session)
        path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        return path

    def load_recording(self, path: Path) -> dict[str, Any]:
        """Load a previously persisted playback recording."""

        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            return payload
        return {}


__all__ = ["SessionVcrService"]
