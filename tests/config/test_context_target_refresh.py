"""Target-specific refresh must keep sibling repository instructions isolated."""

from pathlib import Path
from typing import Any

import pytest

from henchman.config.context import ContextLoader


@pytest.mark.parametrize("git_repo", [True, False])
def test_context_target_refresh_keeps_sibling_scopes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, git_repo: bool,
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(Path, "home", lambda: home)
    root = (tmp_path / "project").resolve()
    root.mkdir(parents=True)
    if git_repo:
        (root / ".git").mkdir()
    root_source = root / "HENCHMAN.md"
    root_source.write_text("ROOT marker", encoding="utf-8")
    left, right = root / "left", root / "right"
    for directory, marker in [(left, "LEFT marker"), (right, "RIGHT marker")]:
        directory.mkdir()
        (directory / "AGENTS.md").write_text(marker, encoding="utf-8")
        (directory / "task.py").write_text("pass\n", encoding="utf-8")
    loader = ContextLoader(start_dir=root, include_subdirs=True)
    left_snapshot = loader.load_for_path(left / "task.py")
    captured_left = left_snapshot.content
    right_snapshot = loader.load_for_path(right / "task.py")
    assert [source.path for source in left_snapshot.sources] == [root_source, left / "AGENTS.md"]
    assert [source.scope for source in left_snapshot.sources] == [root, left]
    assert [source.path for source in right_snapshot.sources] == [root_source, right / "AGENTS.md"]
    assert [source.scope for source in right_snapshot.sources] == [root, right]
    assert "LEFT marker" in captured_left and "RIGHT marker" not in captured_left
    assert "RIGHT marker" in right_snapshot.content and "LEFT marker" not in right_snapshot.content
    assert left_snapshot.content == captured_left


def test_context_target_refresh_rejects_outside_before_reading(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(Path, "home", lambda: home)
    root = (tmp_path / "project").resolve()
    (root / ".git").mkdir(parents=True)
    (root / "HENCHMAN.md").write_text("Project instructions", encoding="utf-8")
    outside = root.with_name(root.name + "-other")
    outside.mkdir()
    (outside / ".git").mkdir()
    outside_source = outside / "AGENTS.md"
    outside_source.write_text("OUTSIDE instructions", encoding="utf-8")
    target = outside / "task.py"
    target.write_text("pass\n", encoding="utf-8")
    original_read = Path.read_text

    def guarded_read(path: Path, *args: Any, **kwargs: Any) -> str:
        if path.resolve() == outside_source.resolve():
            pytest.fail("Outside instruction file was read before rejection")
        return original_read(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", guarded_read)
    loader = ContextLoader(start_dir=root)
    with pytest.raises(ValueError, match="outside"):
        loader.load_for_path(target)
