"""Instruction provenance snapshots capture file data and discovery order."""

from pathlib import Path

import pytest

from henchman.config.context import ContextLoader


@pytest.fixture
def instruction_tree(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> tuple[ContextLoader, list[tuple[Path, Path, str, str]]]:
    home = tmp_path / "home"
    global_root = home / ".henchman"
    global_root.mkdir(parents=True)
    monkeypatch.setattr(Path, "home", lambda: home)
    root = (tmp_path / "project").resolve()
    child = root / "child"
    child.mkdir(parents=True)
    (root / ".git").mkdir()
    sources = [
        (global_root / "HENCHMAN.md", global_root, "global", "Global instructions"),
        (root / "HENCHMAN.md", root, "repository", "Root Henchman instructions"),
        (root / "AGENTS.md", root, "repository", "Root portable instructions"),
        (child / "AGENTS.md", child, "repository", "Child portable instructions"),
    ]
    for path, _, _, content in sources:
        path.write_text(content, encoding="utf-8")
    return ContextLoader(start_dir=child), sources


def test_load_snapshot_fields_and_content(
    instruction_tree: tuple[ContextLoader, list[tuple[Path, Path, str, str]]],
) -> None:
    loader, expected = instruction_tree
    snapshot = loader.load_snapshot()
    assert isinstance(snapshot.sources, tuple)
    assert [
        (source.path, source.scope, source.kind, source.order, source.content)
        for source in snapshot.sources
    ] == [
        (path, scope, kind, order, content)
        for order, (path, scope, kind, content) in enumerate(expected)
    ]
    rendered = "\n\n---\n\n".join(
        f"# Context: {path}\n{content}" for path, _, _, content in expected
    )
    assert snapshot.content == rendered == loader.load()


def test_snapshot_updates_on_edit(
    instruction_tree: tuple[ContextLoader, list[tuple[Path, Path, str, str]]],
) -> None:
    loader, expected = instruction_tree
    original = loader.load_snapshot()
    original_rendered = original.content
    path, _, _, old_content = expected[-1]
    path.write_text("Updated child instructions", encoding="utf-8")
    updated = loader.load_snapshot()
    assert original.sources[-1].content == old_content
    assert original.content == original_rendered
    assert "Updated child instructions" not in original.content
    assert updated.sources[-1].content == "Updated child instructions"
    assert "Updated child instructions" in updated.content
    assert updated.content != original.content
