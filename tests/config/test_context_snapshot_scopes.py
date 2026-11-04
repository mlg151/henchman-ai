"""Instruction metadata follows original discovery paths and filename scopes."""

from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from henchman.config.context import ContextLoader


@pytest.mark.parametrize(
    ("filename", "is_symlink"),
    [(".github/copilot-instructions.md", False), ("rules/HENCHMAN.md", False), ("AGENTS.md", True)],
)
def test_context_snapshot_scopes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, filename: str, is_symlink: bool,
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(Path, "home", lambda: home)
    project = (tmp_path / "project").resolve()
    project.mkdir()
    (project / ".git").mkdir()
    path = project / filename
    content = f"Instructions for {filename}: café"
    if is_symlink:
        target = project / "private" / "instructions.md"
        target.parent.mkdir()
        target.write_text(content, encoding="utf-8")
        try:
            path.symlink_to(target)
        except (OSError, NotImplementedError):
            pytest.skip("Symlink creation is unavailable")
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    loader = ContextLoader(filenames=("HENCHMAN.md", filename), start_dir=project)
    snapshot = loader.load_snapshot()
    assert isinstance(snapshot.sources, tuple)
    assert len(snapshot.sources) == 1
    source = snapshot.sources[0]
    assert (source.path, source.scope, source.kind, source.order, source.content) == (
        path, project, "repository", 0, content,
    )
    assert snapshot.content == f"# Context: {path}\n{content}"
    with pytest.raises(FrozenInstanceError):
        source.order = 99
