"""Bounded instruction capture and truncation diagnostics."""

from pathlib import Path

import pytest

from henchman.config.context import ContextLoader


@pytest.fixture
def instruction_tree(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> tuple[Path, Path]:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(Path, "home", lambda: home)
    project = (tmp_path / "project").resolve()
    project.mkdir()
    (project / ".git").mkdir()
    return home, project


def test_snapshot_diagnostics_report_order_size_and_scope(
    instruction_tree: tuple[Path, Path],
) -> None:
    _, project = instruction_tree
    (project / "HENCHMAN.md").write_text("Root instructions", encoding="utf-8")
    child = project / "child"
    child.mkdir()
    (child / "AGENTS.md").write_text("Child agent instructions", encoding="utf-8")

    snapshot = ContextLoader(start_dir=child).load_snapshot()

    diagnostics = snapshot.diagnostics()
    assert [d.order for d in diagnostics] == list(range(len(diagnostics)))
    by_scope = {d.scope: d for d in diagnostics}
    assert by_scope[project].chars == len("Root instructions")
    assert by_scope[child].chars == len("Child agent instructions")
    assert all(d.original_chars == d.chars for d in diagnostics)
    assert all(not d.truncated for d in diagnostics)
    assert snapshot.truncated_sources == ()


def test_source_truncation_caps_capture_and_renders_marker(
    instruction_tree: tuple[Path, Path],
) -> None:
    _, project = instruction_tree
    body = "A" * 100
    (project / "HENCHMAN.md").write_text(body, encoding="utf-8")

    loader = ContextLoader(start_dir=project, max_source_chars=40)
    snapshot = loader.load_snapshot()

    source = snapshot.sources[0]
    assert source.original_chars == 100
    assert source.truncated is True
    assert source.content.startswith("A" * 40)
    assert "40 of 100" in source.content
    assert snapshot.truncated_sources == (source,)
    assert snapshot.content.count("# Context:") == 1
    assert body not in snapshot.content


def test_total_render_stays_bounded_with_multiple_truncated_sources(
    instruction_tree: tuple[Path, Path],
) -> None:
    _, project = instruction_tree
    for name in ("HENCHMAN.md", "AGENTS.md"):
        (project / name).write_text(name[0] * 500, encoding="utf-8")

    snapshot = ContextLoader(start_dir=project, max_source_chars=50).load_snapshot()

    assert all(source.truncated for source in snapshot.sources)
    assert sum(len(source.content) for source in snapshot.sources) < 500
    diagnostics = {d.order: d for d in snapshot.diagnostics()}
    assert all(d.truncated for d in diagnostics.values())


def test_max_source_chars_validation(instruction_tree: tuple[Path, Path]) -> None:
    _, project = instruction_tree
    with pytest.raises(ValueError, match="max_source_chars"):
        ContextLoader(start_dir=project, max_source_chars=0)
    with pytest.raises(ValueError, match="max_source_chars"):
        ContextLoader(start_dir=project, max_source_chars=-1)


def test_snapshot_digest_is_stable_and_content_sensitive(
    instruction_tree: tuple[Path, Path],
) -> None:
    _, project = instruction_tree
    (project / "HENCHMAN.md").write_text("Digest body", encoding="utf-8")
    first = ContextLoader(start_dir=project).load_snapshot()
    second = ContextLoader(start_dir=project).load_snapshot()
    assert first.digest == second.digest
    (project / "HENCHMAN.md").write_text("Digest body changed", encoding="utf-8")
    third = ContextLoader(start_dir=project).load_snapshot()
    assert third.digest != first.digest


def test_snapshot_to_dict_is_metadata_only_by_default(
    instruction_tree: tuple[Path, Path],
) -> None:
    _, project = instruction_tree
    (project / "HENCHMAN.md").write_text("Roundtrip instructions", encoding="utf-8")
    snapshot = ContextLoader(start_dir=project).load_snapshot()

    payload = snapshot.to_dict()

    assert payload["digest"] == snapshot.digest
    assert [source["path"] for source in payload["sources"]] == [str(snapshot.sources[0].path)]
    assert all("content" not in source for source in payload["sources"])
    assert all(len(source["sha256"]) == 64 for source in payload["sources"])
    assert "Roundtrip instructions" not in str(payload)


def test_snapshot_to_dict_can_include_content(
    instruction_tree: tuple[Path, Path],
) -> None:
    _, project = instruction_tree
    (project / "HENCHMAN.md").write_text("Detailed instructions", encoding="utf-8")
    snapshot = ContextLoader(start_dir=project).load_snapshot()

    payload = snapshot.to_dict(include_content=True)

    assert payload["content"] == snapshot.content
    assert payload["sources"][0]["content"] == "Detailed instructions"
    assert payload["digest"] == snapshot.digest
