"""End-to-end wiring: Repl captures instruction provenance for sessions."""

from io import StringIO
from pathlib import Path
from unittest.mock import patch

import pytest
from rich.console import Console

from henchman.cli.repl import Repl, ReplConfig
from henchman.config.context import ContextLoader
from henchman.core.instruction_provenance import INSTRUCTION_PROVENANCE_KEY
from tests.cli.test_repl import MockProvider


def test_repl_captures_provenance_on_session_attach(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(Path, "home", lambda: home)
    project = (tmp_path / "project").resolve()
    project.mkdir()
    (project / ".git").mkdir()
    (project / "AGENTS.md").write_text("Integration provenance instructions", encoding="utf-8")
    monkeypatch.chdir(project)
    snapshot = ContextLoader(start_dir=project).load_snapshot()

    with patch("henchman.cli.input.PromptSession"):
        console = Console(file=StringIO(), force_terminal=True)
        config = ReplConfig(
            system_prompt=snapshot.content,
            auto_save=False,
            interactive=False,
            instruction_snapshot=snapshot,
        )
        repl = Repl(provider=MockProvider(), console=console, config=config)

    project_hash = repl.session_manager.compute_project_hash(Path.cwd())
    session = repl.session_manager.create_session(project_hash)
    repl.set_session(session)

    record = session.export_metadata.get(INSTRUCTION_PROVENANCE_KEY)
    assert record is not None
    assert record["digest"] == snapshot.digest
    assert [source["path"] for source in record["sources"]] == [
        str(source.path) for source in snapshot.sources
    ]
    assert "Integration provenance instructions" not in str(record)
