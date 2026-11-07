"""Canary secrets must not enter session evidence or derived persistent copies."""

import json
from pathlib import Path

import pytest

from henchman.core.goals import GoalService
from henchman.core.instruction_provenance import InstructionProvenanceService
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


@pytest.mark.parametrize("secret", ["id", "a", "user", "started", "project_hash", "active", "digest"])
def test_short_credentials_preserve_protocol_fields_and_identity(tmp_path: Path, secret: str) -> None:
    manager = SessionManager(tmp_path, evidence_redactor=EvidenceRedactor([secret]))
    session = manager.create_session("project-a")
    message = SessionMessage(role="user", content=f"Echo: {secret}", tool_calls=[{
        "id": "call-id", "name": "read_file", "arguments": {"password": secret},
    }])
    session.messages.append(message)
    session.turn_summaries.append(TurnSummaryRecord(
        turn_number=1, summary_text=f"Credential: {secret}", kind="compaction",
        retained_messages=[message], source_turns=[1],
    ))
    memory = SessionMemoryService().add_memory(session, content=f"Echo: {secret}")
    goal = GoalService().start(session, f"Echo: {secret}")
    SessionMemoryService().set_extraction_opt_out(session, True)
    session.export_metadata["instruction_sources"] = {
        "version": 1, "captured_at": session.started, "digest": "a" * 64,
        "sources": [{"path": "/repo/a/AGENTS.md", "scope": "/repo/a", "kind": "repository",
                     "order": 0, "chars": 2, "original_chars": 2, "truncated": False,
                     "sha256": "b" * 64}],
    }
    path = manager.save(session)
    manager.save(session)
    loaded = manager.load(session.id, project_hash="project-a")
    assert loaded.id == session.id
    assert loaded.started == session.started
    assert loaded.messages[0].role == "user"
    assert loaded.messages[0].content == "Echo: [REDACTED]"
    assert loaded.messages[0].tool_calls[0]["id"] == "call-id"
    assert loaded.messages[0].tool_calls[0]["name"] == "read_file"
    assert loaded.turn_summaries[0].retained_messages[0].role == "user"
    restored_memory = SessionMemoryService().list_memories(loaded)[0]
    assert restored_memory.id == memory.id
    assert restored_memory.content == "Echo: [REDACTED]"
    assert SessionMemoryService().extraction_opt_out(loaded)
    restored_goal = GoalService().get(loaded)
    assert restored_goal.id == goal.id
    assert restored_goal.status == "active"
    assert restored_goal.objective == "Echo: [REDACTED]"
    assert InstructionProvenanceService().get(loaded)["digest"] == "a" * 64
    template = manager.save_template(session.id, "example")
    assert template["session_data"]["id"] == session.id
    derived = manager.create_from_template(template["id"], project_hash="project-a")
    assert derived.project_hash == "project-a"
    assert json.loads(path.with_suffix(".json.bak").read_text())["id"] == session.id


def test_marker_containing_secret_is_removed_from_saved_echo(tmp_path: Path) -> None:
    secret = "secret-[REDACTED]-canary"
    manager = SessionManager(tmp_path, evidence_redactor=EvidenceRedactor([secret]))
    session = manager.create_session("project")
    session.messages.append(SessionMessage(role="user", content=secret))
    assert secret not in manager.save(session).read_text()


def test_backup_only_credential_masks_current_copy_echoes(tmp_path: Path) -> None:
    manager = SessionManager(tmp_path)
    session = manager.create_session("project")
    payload = session.to_dict()
    secret = "credential-found-only-in-old-backup"
    payload["messages"] = [{"role": "user", "content": secret}]
    path = tmp_path / f"{session.id}.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    payload["export_metadata"] = {"password": secret}
    path.with_suffix(".json.bak").write_text(json.dumps(payload), encoding="utf-8")
    loaded = manager.load(session.id)
    manager.save(loaded)
    assert secret not in path.read_text()
    assert secret not in path.with_suffix(".json.bak").read_text()


def test_memory_kind_and_source_are_evidence_text(tmp_path: Path) -> None:
    secret = "known-memory-source-canary"
    manager = SessionManager(tmp_path, evidence_redactor=EvidenceRedactor([secret]))
    session = manager.create_session("project")
    memory = SessionMemoryService().add_memory(session, content="ordinary", kind=secret, source=secret)
    assert secret not in session.to_json()
    manager.save(session)
    loaded = SessionMemoryService().list_memories(manager.load(session.id))[0]
    assert loaded.id == memory.id
    assert loaded.kind == loaded.source == "[REDACTED]"


def test_extra_storage_metadata_cannot_bypass_backup_redaction(tmp_path: Path) -> None:
    secret = "legacy-storage-metadata-canary"
    manager = SessionManager(tmp_path)
    session = manager.create_session("project")
    path = manager.save(session)
    payload = json.loads(path.read_text())
    # Storage metadata is outside the payload checksum. Extra legacy fields
    # are accepted on read, but cannot bypass the retained-copy policy.
    payload["_storage"]["password"] = secret
    path.write_text(json.dumps(payload), encoding="utf-8")
    manager.save(manager.load(session.id))
    assert secret not in path.read_text()
    assert secret not in path.with_suffix(".json.bak").read_text()


def test_invalid_identity_container_is_not_persisted(tmp_path: Path) -> None:
    manager = SessionManager(tmp_path)
    session = manager.create_session("project")
    session.active_agents = [{"api_key": "hidden-canary"}]  # type: ignore[list-item]
    with pytest.raises(ValueError, match="Protocol identity"):
        manager.save(session)
    assert not (tmp_path / f"{session.id}.json").exists()
