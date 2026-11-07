"""Dynamic subagents inherit bounded project instruction provenance."""

from io import StringIO
from pathlib import Path
from unittest.mock import patch

import pytest
from rich.console import Console

from henchman.cli.repl import Repl, ReplConfig
from henchman.config.context import ContextLoader
from tests.cli.test_repl import MockProvider


@pytest.mark.asyncio
async def test_spawned_subagent_receives_provenance_appendix(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(Path, "home", lambda: home)
    project = (tmp_path / "project").resolve()
    project.mkdir()
    (project / ".git").mkdir()
    (project / "AGENTS.md").write_text(
        "Subagent provenance instructions", encoding="utf-8",
    )
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

    assert repl.orchestrator.instruction_snapshot is snapshot
    manager = repl.orchestrator.subagents
    record = manager.spawn(
        "Inspect the repository",
        role="reviewer",
        system_prompt="Review only.",
        tools=[],
    )
    conversation = manager._conversations[record.conversation_id]  # noqa: SLF001
    child_prompt = conversation.agent.system_prompt

    assert "Review only." in child_prompt
    assert "Project instruction provenance" in child_prompt
    assert str(project / "AGENTS.md") in child_prompt
    assert "Subagent provenance instructions" not in child_prompt
    assert "tool policy" in child_prompt
    await manager.close()


@pytest.mark.asyncio
async def test_spawned_subagent_without_snapshot_gets_prompt_verbatim(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(Path, "home", lambda: home)
    project = (tmp_path / "project").resolve()
    project.mkdir()
    (project / "AGENTS.md").write_text("Ignored without snapshot fixture", encoding="utf-8")
    monkeypatch.chdir(project)

    with patch("henchman.cli.input.PromptSession"):
        console = Console(file=StringIO(), force_terminal=True)
        config = ReplConfig(
            system_prompt="",
            auto_save=False,
            interactive=False,
        )
        repl = Repl(provider=MockProvider(), console=console, config=config)

    manager = repl.orchestrator.subagents
    record = manager.spawn(
        "Inspect the repository",
        role="reviewer",
        system_prompt="Review only.",
        tools=[],
    )
    conversation = manager._conversations[record.conversation_id]  # noqa: SLF001
    assert conversation.agent.system_prompt == "Review only."
    await manager.close()
