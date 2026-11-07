"""Canary secrets must not enter session evidence or derived persistent copies."""

import json
from pathlib import Path

import pytest

from henchman.core.session import SessionManager, SessionMessage, TurnSummaryRecord
from henchman.core.session_export import export_as_markdown
from henchman.core.session_memory import SessionMemoryService
from henchman.core.session_vcr import SessionVcrService
from henchman.utils.evidence_redaction import EvidenceRedactor


def test_configured_environment_secret_redacted_before_disk_and_export(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    secret = "canary-private-provider-credential"
    monkeypatch.setenv("OPENROUTER_API_KEY", secret)
    manager = SessionManager(tmp_path)
    session = manager.create_session("project")
    session.messages.append(SessionMessage(role="user", content=f"Error echoed {secret}"))
    session.export_metadata["nested"] = {"Authorization": "Bearer marked-header-canary"}
    path = manager.save(session)
    manager.save(session)
    for saved in (path, path.with_suffix(".json.bak")):
        text = saved.read_text()
        assert secret not in text
        assert "marked-header-canary" not in text
        assert "[REDACTED]" in text
    assert secret not in session.to_json()
    assert secret not in export_as_markdown(session)
    assert session.messages[0].content == f"Error echoed {secret}"  # Execution input is unchanged.
    assert "[REDACTED]" in manager.load(session.id).messages[0].content


def test_legacy_backup_and_template_cannot_retain_configured_secret(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    manager = SessionManager(tmp_path)
    session = manager.create_session("project")
    secret = "legacy-provider-secret-canary"
    session.messages.append(SessionMessage(role="assistant", content=secret))
    # Create a pre-redaction legacy file without calling the new serializer.
    payload = session.to_dict()
    payload["messages"][0]["content"] = secret
    path = tmp_path / f"{session.id}.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setenv("OPENAI_API_KEY", secret)
    loaded = manager.load(session.id)
    manager.save(loaded)
    template = manager.save_template(session.id, "example", project_hash="project")
    for artifact in (path, path.with_suffix(".json.bak"), tmp_path / "templates" / f"{template['id']}.json"):
        assert secret not in artifact.read_text()
    assert secret not in manager.export_session(session.id)


def test_playback_does_not_record_secret_tool_arguments(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    secret = "playback-private-key-canary"
    monkeypatch.setenv("OPENAI_API_KEY", secret)
    session = SessionManager(tmp_path).create_session("project")
    session.messages.append(SessionMessage(role="assistant", tool_calls=[{
        "id": "call-1", "name": "request", "arguments": {"api_key": secret}
    }]))
    playback = SessionVcrService().build_playback(session)
    assert secret not in json.dumps(playback)


@pytest.mark.parametrize("missing_current", [False, True])
def test_recovery_sanitizes_retained_legacy_backup(tmp_path: Path, missing_current: bool) -> None:
    secret = "recovered-configured-secret-canary"
    manager = SessionManager(tmp_path, evidence_redactor=EvidenceRedactor([secret]))
    session = manager.create_session("project")
    payload = session.to_dict()
    payload["messages"] = [{"role": "assistant", "content": secret}]
    path = tmp_path / f"{session.id}.json"
    backup = path.with_suffix(".json.bak")
    backup.write_text(json.dumps(payload), encoding="utf-8")
    if not missing_current:
        path.write_text("broken", encoding="utf-8")
    with pytest.warns(UserWarning, match="Recovered prior session"):
        recovered = manager.load(session.id)
    manager.save(recovered)
    assert secret not in path.read_text()
    assert secret not in backup.read_text()
    # A second save checks that the optimistic revision includes sanitized bytes.
    manager.save(recovered)
    assert "[REDACTED]" in manager.load(session.id).messages[0].content


def test_template_metadata_and_derived_sessions_share_configured_policy(tmp_path: Path) -> None:
    secret = "configured-not-environment-canary"
    manager = SessionManager(tmp_path, evidence_redactor=EvidenceRedactor([secret]))
    session = manager.create_session("project")
    manager.save(session)
    template = manager.save_template(
        session.id, secret, description=secret, parameters={"password": "marked-canary"},
    )
    assert secret not in json.dumps(template)
    assert "marked-canary" not in json.dumps(template)
    assert secret not in (tmp_path / "templates" / f"{template['id']}.json").read_text()
    derived = [
        manager.branch_session(session.id, 0),
        manager.import_session(session.to_json()),
        manager.create_from_template(template["id"]),
        manager.merge_sessions([session.id, session.id]),
    ]
    for item in derived:
        item.messages.append(SessionMessage(role="user", content=secret))
        assert secret not in item.to_json()
        assert item.messages[-1].content == secret


def test_removed_legacy_credential_still_masks_current_echo(tmp_path: Path) -> None:
    manager = SessionManager(tmp_path)
    session = manager.create_session("project")
    secret = "removed-credential-still-echoed-canary"
    payload = session.to_dict()
    payload["export_metadata"] = {"password": secret}
    payload["messages"] = [{"role": "user", "content": secret}]
    path = tmp_path / f"{session.id}.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    loaded = manager.load(session.id)
    loaded.export_metadata.clear()
    manager.save(loaded)
    assert secret not in path.read_text()
    assert secret not in path.with_suffix(".json.bak").read_text()


def test_retained_turns_memories_and_playback_share_marked_secrets(tmp_path: Path) -> None:
    manager = SessionManager(tmp_path)
    session = manager.create_session("project")
    secret = "marked-outside-playback-canary"
    session.export_metadata["password"] = secret
    session.messages.append(SessionMessage(role="assistant", content=secret, reasoning_content=secret))
    session.turn_summaries.append(TurnSummaryRecord(
        turn_number=1, summary_text=secret, kind="compaction", source_turns=[1],
        retained_messages=[SessionMessage(role="tool", content=secret, tool_call_id="call-1")],
    ))
    SessionMemoryService().add_memory(session, content=secret)
    playback = SessionVcrService().record_session(session, tmp_path / "playback.json")
    assert secret not in playback.read_text()
    path = manager.save(session)
    assert secret not in path.read_text()
    assert secret not in export_as_markdown(session)
    assert session.turn_summaries[0].retained_messages[0].content == secret
