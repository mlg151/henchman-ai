"""Compaction records must keep original turns recoverable."""

from __future__ import annotations

from pathlib import Path

from henchman.core.session import SessionManager, SessionMessage
from henchman.core.session_context import SessionContextService
from henchman.core.session_models import turn_summary_from_dict


def _build_session(manager: SessionManager) -> object:
    """Persist a two-turn session with a tool call/result pair in turn 1."""

    session = manager.create_session(project_hash="abc123", tag="compact")
    session.messages = [
        SessionMessage(role="user", content="First request."),
        SessionMessage(
            role="assistant",
            content="Reading the file.",
            tool_calls=[{"id": "tc1", "name": "read_file", "arguments": {"path": "a.txt"}}],
        ),
        SessionMessage(role="tool", content="file contents", tool_call_id="tc1"),
        SessionMessage(role="assistant", content="Done reading."),
        SessionMessage(role="user", content="Second request."),
        SessionMessage(role="assistant", content="Final answer."),
    ]
    manager.save(session)
    return session


def _restore(manager: SessionManager, session: object) -> list[dict]:
    """Restore the full message sequence and return dict form for comparison."""

    service = SessionContextService(manager)
    restored = service.restore_compacted_messages(session)
    return [message.to_dict() for message in restored]


def test_compaction_record_references_source_turns_and_retains_messages(
    tmp_path: Path,
) -> None:
    """The compaction record must name the dropped turns and retain their messages."""

    manager = SessionManager(data_dir=tmp_path / "sessions")
    session = _build_session(manager)
    service = SessionContextService(manager)

    result = service.compact_session(session, preserve_turns=1)

    assert result.changed is True
    record = session.turn_summaries[-1]
    assert record.kind == "compaction"
    assert record.source_turns == [1]
    retained = [message.to_dict() for message in record.retained_messages]
    # The dropped turn's tool pair must be preserved verbatim.
    assert retained[0] == {"role": "user", "content": "First request."}
    assert retained[2] == {
        "role": "tool",
        "content": "file contents",
        "tool_call_id": "tc1",
    }
    assert len(retained) == 4


def test_restored_messages_reconstruct_original_sequence(tmp_path: Path) -> None:
    """Restoring compacted turns must return the exact original message sequence."""

    manager = SessionManager(data_dir=tmp_path / "sessions")
    session = _build_session(manager)
    original = [message.to_dict() for message in session.messages]
    service = SessionContextService(manager)

    service.compact_session(session, preserve_turns=1)

    assert _restore(manager, session) == original


def test_restored_tool_pairs_remain_valid(tmp_path: Path) -> None:
    """Every retained tool result must pair with its assistant tool call."""

    manager = SessionManager(data_dir=tmp_path / "sessions")
    session = _build_session(manager)
    service = SessionContextService(manager)

    service.compact_session(session, preserve_turns=1)
    restored = service.restore_compacted_messages(session)

    seen_call_ids: set[str] = set()
    for message in restored:
        for tool_call in message.tool_calls or []:
            if isinstance(tool_call, dict) and isinstance(tool_call.get("id"), str):
                seen_call_ids.add(tool_call["id"])
        if message.role == "tool" and message.tool_call_id:
            assert message.tool_call_id in seen_call_ids


def test_compaction_retained_messages_survive_save_load(tmp_path: Path) -> None:
    """Retention must persist across a save/load round trip."""

    manager = SessionManager(data_dir=tmp_path / "sessions")
    session = _build_session(manager)
    original = [message.to_dict() for message in session.messages]
    service = SessionContextService(manager)

    service.compact_session(session, preserve_turns=1)
    manager.save(session)
    loaded = manager.load(session.id)

    assert _restore(manager, loaded) == original


def test_double_compaction_restores_full_history(tmp_path: Path) -> None:
    """Successive compactions must keep every dropped turn retrievable."""

    manager = SessionManager(data_dir=tmp_path / "sessions")
    session = manager.create_session(project_hash="abc123", tag="compact2")
    session.messages = [
        SessionMessage(role="user", content="Turn one."),
        SessionMessage(role="assistant", content="One done."),
        SessionMessage(role="user", content="Turn two."),
        SessionMessage(role="assistant", content="Two done."),
        SessionMessage(role="user", content="Turn three."),
        SessionMessage(role="assistant", content="Three done."),
        SessionMessage(role="user", content="Turn four."),
        SessionMessage(role="assistant", content="Four done."),
    ]
    manager.save(session)
    original = [message.to_dict() for message in session.messages]
    service = SessionContextService(manager)

    service.compact_session(session, preserve_turns=3)
    expected = list(original)
    expected.append({"role": "user", "content": "Turn five."})
    expected.append({"role": "assistant", "content": "Five done."})
    session.messages.append(SessionMessage(role="user", content="Turn five."))
    session.messages.append(SessionMessage(role="assistant", content="Five done."))
    service.compact_session(session, preserve_turns=3)

    assert _restore(manager, session) == expected


def test_legacy_turn_summary_dict_loads_with_documented_defaults() -> None:
    """Old-format records must load with kind='turn' and empty retention fields."""

    record = turn_summary_from_dict(
        {
            "turn_number": 1,
            "summary_text": "Legacy summary",
            "files_modified": ["a.txt"],
            "tool_count": 1,
            "timestamp": "2026-01-01T00:00:00+00:00",
        }
    )

    assert record.kind == "turn"
    assert record.source_turns == []
    assert record.retained_messages == []
