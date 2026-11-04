"""Physical instruction boundaries apply to all supported discovery layouts."""

from pathlib import Path

import pytest

from henchman.config.context import ContextLoader


@pytest.mark.parametrize("mode", ["global", "non-git", "worktree"])
def test_context_discovery_boundaries(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mode: str,
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(Path, "home", lambda: home)
    project = (tmp_path / "project").resolve()
    project.mkdir()
    if mode == "worktree":
        (project / ".git").write_text("gitdir: ../git-metadata", encoding="utf-8")
    candidate_root = home / ".henchman" if mode == "global" else project
    candidate_root.mkdir(exist_ok=True)
    marker = f"Unique local instruction for {mode}"
    source = candidate_root / "HENCHMAN.md"
    source.write_text(marker, encoding="utf-8")
    outside = tmp_path / "outside.md"
    outside.write_text("Outside instruction marker", encoding="utf-8")
    github = candidate_root / ".github"
    github.mkdir()
    try:
        (candidate_root / "AGENTS.md").symlink_to(source)
        (github / "copilot-instructions.md").symlink_to(outside)
    except (OSError, NotImplementedError):
        pytest.skip("Symlink creation is unavailable")

    loader = ContextLoader(start_dir=project)
    assert loader.discover_files() == [source]
    content = loader.load()
    assert content.count(marker) == 1
    assert "Outside instruction marker" not in content
