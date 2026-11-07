from pathlib import Path

import pytest

from henchman.config.context import ContextLoader


@pytest.mark.parametrize("git_repo", [True, False])
def test_portable_agents_context(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    git_repo: bool,
) -> None:
    workspace = (tmp_path / "workspace").resolve()
    workspace.mkdir()

    root = workspace
    henchman_root = root / "HENCHMAN.md"
    agents_root = root / "AGENTS.md"

    child = workspace / "child"
    child.mkdir()
    henchman_child = child / "HENCHMAN.md"
    agents_child = child / "AGENTS.md"

    sibling = workspace / "sibling"
    sibling.mkdir()
    agents_sibling = sibling / "AGENTS.md"

    henchman_root.write_text("Marker root HENCHMAN", encoding="utf-8")
    agents_root.write_text("Marker root AGENTS", encoding="utf-8")
    henchman_child.write_text("Marker child HENCHMAN", encoding="utf-8")
    agents_child.write_text("Marker child AGENTS", encoding="utf-8")
    agents_sibling.write_text("Marker sibling AGENTS", encoding="utf-8")

    if git_repo:
        (workspace / ".git").mkdir()

    mock_home = tmp_path / ".home"
    mock_home.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr("pathlib.Path.home", lambda: mock_home)

    loader = ContextLoader(start_dir=child)

    discovered = loader.discover_files()

    assert henchman_child in discovered

    assert loader.filename == "HENCHMAN.md"

    assert agents_child in discovered
    content = loader.load()
    assert "Marker child AGENTS" in content

    if git_repo:
        assert agents_root in discovered
        assert henchman_root in discovered
    else:
        assert agents_root not in discovered
        assert henchman_root not in discovered

    assert agents_sibling not in discovered
