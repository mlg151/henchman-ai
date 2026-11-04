"""Instruction discovery preserves physical-file and repository boundaries."""

from pathlib import Path

import pytest

from henchman.config.context import ContextLoader


@pytest.fixture
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(Path, "home", lambda: home)
    root = (tmp_path / "project").resolve()
    root.mkdir()
    (root / ".git").mkdir()
    return root


def test_symlink_same_file(project: Path) -> None:
    """Retain the first filename and read a shared physical source once."""
    source = project / "HENCHMAN.md"
    marker = "Unique shared instruction marker"
    source.write_text(marker, encoding="utf-8")
    alias = project / "AGENTS.md"
    try:
        alias.symlink_to(source)
    except (OSError, NotImplementedError):
        pytest.skip("Symlink creation is unavailable")

    loader = ContextLoader(start_dir=project)
    assert loader.discover_files() == [source]
    assert loader.load().count(marker) == 1


def test_symlink_outside_git_root(project: Path, tmp_path: Path) -> None:
    """Reject an escaped source while retaining local instructions."""
    source = project / "HENCHMAN.md"
    source.write_text("Local instruction marker", encoding="utf-8")
    outside = tmp_path / "outside.md"
    outside.write_text("Escaped instruction marker", encoding="utf-8")
    alias = project / "AGENTS.md"
    try:
        alias.symlink_to(outside)
    except (OSError, NotImplementedError):
        pytest.skip("Symlink creation is unavailable")

    loader = ContextLoader(start_dir=project)
    files = loader.discover_files()
    assert files == [source]
    assert all(path.resolve() != outside.resolve() for path in files)
    content = loader.load()
    assert "Local instruction marker" in content
    assert "Escaped instruction marker" not in content
