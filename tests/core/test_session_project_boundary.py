"""Project-scoped lookup must protect transcripts and derived artifacts."""

from pathlib import Path

import pytest

from henchman.core.session import SessionManager, SessionMessage
from henchman.core.session_context import SessionContextService


@pytest.mark.parametrize("selector", ["foreign-session", "foreign"])
def test_scoped_lookup_and_derivatives_reject_foreign_session(
    tmp_path: Path, selector: str
) -> None:
    manager = SessionManager(tmp_path)
    foreign = manager.create_session("other")
    foreign.id = "foreign-session"
    foreign.messages.append(SessionMessage(role="user", content="PRIVATE OTHER PROJECT"))
    path = manager.save(foreign)
    original = path.read_bytes()
    actions = [
        lambda: manager.load(selector, project_hash="own"),
        lambda: manager.export_session(selector, project_hash="own"),
        lambda: manager.branch_session(selector, 1, project_hash="own"),
        lambda: manager.merge_sessions([selector, selector], project_hash="own"),
        lambda: manager.save_template(selector, "leak", project_hash="own"),
    ]
    for action in actions:
        with pytest.raises(FileNotFoundError, match="current project"):
            action()
    assert path.read_bytes() == original
    assert not (tmp_path / "templates").exists()
    assert manager.load(foreign.id).messages == foreign.messages  # Explicit unscoped core access.


def test_prefix_resolution_ignores_foreign_collisions(tmp_path: Path) -> None:
    manager = SessionManager(tmp_path)
    for suffix, project in (("one", "own"), ("two", "other")):
        session = manager.create_session(project)
        session.id = f"same-{suffix}"
        manager.save(session)
    assert manager.load("same", project_hash="own").id == "same-one"
    with pytest.raises(ValueError, match="Ambiguous"):
        manager.load("same")


def test_context_cannot_follow_foreign_current_pointer(tmp_path: Path) -> None:
    manager = SessionManager(tmp_path / "sessions")
    project_hash = manager.compute_project_hash(tmp_path / "project")
    own = manager.create_session(project_hash)
    foreign = manager.create_session("other")
    foreign.messages.append(SessionMessage(role="user", content="PRIVATE OTHER PROJECT"))
    manager.save(own)
    manager.save(foreign)
    manager.set_project_current(project_hash, foreign.id)
    _, recovered = SessionContextService(manager).resolve_active_session(tmp_path / "project")
    assert recovered.id == own.id
    assert manager.get_project_current(project_hash) == own.id


def test_existing_templates_remain_project_scoped(tmp_path: Path) -> None:
    manager = SessionManager(tmp_path)
    foreign = manager.create_session("other")
    foreign.messages.append(SessionMessage(role="user", content="PRIVATE OTHER PROJECT"))
    manager.save(foreign)
    template = manager.save_template(foreign.id, "private-template")
    assert manager.list_templates(project_hash="own") == []
    assert manager.list_templates(project_hash="other")[0]["id"] == template["id"]
    for action in (
        lambda: manager.create_from_template(template["id"], project_hash="own"),
        lambda: manager.delete_template(template["id"], project_hash="own"),
    ):
        with pytest.raises(FileNotFoundError, match="current project"):
            action()
    restored = manager.create_from_template(template["id"], project_hash="other")
    assert restored.messages == foreign.messages
    manager.delete_template(template["id"], project_hash="other")
    assert manager.list_templates() == []


@pytest.mark.parametrize("template_id", ["../escape", "x\\y", "glob*"])
def test_template_ids_cannot_escape_storage(tmp_path: Path, template_id: str) -> None:
    manager = SessionManager(tmp_path)
    for action in (manager.create_from_template, manager.delete_template):
        with pytest.raises(ValueError, match="Invalid"):
            action(template_id, project_hash="own")
