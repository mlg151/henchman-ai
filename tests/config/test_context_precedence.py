"""Deterministic precedence and filename compatibility for instruction loading."""

from pathlib import Path

import pytest

from henchman.config.context import DEFAULT_FILENAMES, ContextLoader


def test_default_filenames_keep_henchman_primary() -> None:
    assert DEFAULT_FILENAMES[0] == "HENCHMAN.md"
    assert "AGENTS.md" in DEFAULT_FILENAMES
    assert DEFAULT_FILENAMES.index("AGENTS.md") > DEFAULT_FILENAMES.index("HENCHMAN.md")


def test_same_directory_conflicts_resolve_by_filename_priority(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(Path, "home", lambda: home)
    project = (tmp_path / "project").resolve()
    project.mkdir()
    (project / ".git").mkdir()
    for name in ("HENCHMAN.md", "AGENTS.md", ".gemini/GEMINI.md"):
        path = project / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"Instructions from {name}", encoding="utf-8")

    files = ContextLoader(start_dir=project).discover_files()

    ordered = [path.relative_to(project).as_posix() for path in files]
    assert ordered == ["HENCHMAN.md", ".gemini/GEMINI.md", "AGENTS.md"]


def test_deeper_scope_instructions_render_after_broader_scope(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(Path, "home", lambda: home)
    project = (tmp_path / "project").resolve()
    child = project / "child"
    child.mkdir(parents=True)
    (project / ".git").mkdir()
    (project / "AGENTS.md").write_text("root scope wins ties", encoding="utf-8")
    (child / "AGENTS.md").write_text("deeper scope applies to child", encoding="utf-8")

    snapshot = ContextLoader(start_dir=child).load_snapshot()

    positions = [snapshot.content.index(marker) for marker in (
        "root scope wins ties", "deeper scope applies to child",
    )]
    assert positions == sorted(positions)
    assert [source.scope for source in snapshot.sources] == [project, child]


def test_custom_filenames_resolve_with_custom_priority(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(Path, "home", lambda: home)
    project = (tmp_path / "project").resolve()
    project.mkdir()
    (project / ".git").mkdir()
    (project / "CUSTOM-A.md").write_text("Custom A instructions", encoding="utf-8")
    (project / "CUSTOM-B.md").write_text("Custom B instructions", encoding="utf-8")

    loader = ContextLoader(filenames=("CUSTOM-B.md", "CUSTOM-A.md"), start_dir=project)

    files = loader.discover_files()
    assert [path.name for path in files] == ["CUSTOM-B.md", "CUSTOM-A.md"]


def test_single_legacy_filename_argument_still_supported(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(Path, "home", lambda: home)
    project = (tmp_path / "project").resolve()
    project.mkdir()
    (project / ".git").mkdir()
    (project / "HENCHMAN.md").write_text("Legacy single-file instructions", encoding="utf-8")

    loader = ContextLoader(filename="HENCHMAN.md", start_dir=project)

    assert loader.filename == "HENCHMAN.md"
    assert "Legacy single-file instructions" in loader.load()
