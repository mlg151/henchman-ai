"""CLI runtime consumers carry refreshed instruction provenance and scope."""

import subprocess
from io import StringIO
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from rich.console import Console

from henchman.cli.core_init import create_core_context
from henchman.cli.repl import Repl, ReplConfig
from henchman.config.context import ContextLoader
from henchman.config.schema import Settings
from henchman.core.instruction_provenance import InstructionProvenanceService
from henchman.providers.base import FinishReason, Message, StreamChunk, ToolCall
from tests.cli.test_repl import MockProvider


@pytest.mark.asyncio
@pytest.mark.parametrize("surface", ["repl", "core"])
async def test_runtime_refresh_reaches_session_team_and_dynamic_agents(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, surface: str,
) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path / "home")
    root = tmp_path / "project"
    child = root / "child"
    child.mkdir(parents=True)
    (root / ".git").mkdir()
    (root / "HENCHMAN.md").write_text("ROOT instructions", encoding="utf-8")
    (child / "AGENTS.md").write_text("CHILD instructions", encoding="utf-8")
    (child / "file.txt").write_text("data", encoding="utf-8")
    monkeypatch.chdir(root)
    snapshot = ContextLoader(start_dir=root).load_snapshot()
    settings = Settings()
    settings.agents.allow_delegation = True
    if surface == "core":
        runtime = create_core_context(MockProvider(), settings=settings, instruction_snapshot=snapshot)
    else:
        with patch("henchman.cli.input.PromptSession"):
            runtime = Repl(
                MockProvider(), console=Console(file=StringIO()),
                settings=settings,
                config=ReplConfig(interactive=False, instruction_snapshot=snapshot),
            )
    sessions = runtime.session_manager
    session = sessions.create_session(sessions.compute_project_hash(root))
    sessions.set_session(session, runtime.orchestrator)

    await runtime.agent.tool_registry.execute("read_file", {"path": str(child / "file.txt")})
    prepared, _ = await runtime.agent._prepare_stream_context()
    assert any("CHILD instructions" in (m.content or "") for m in prepared.api_messages)
    service = InstructionProvenanceService()
    record = service.get(session)
    assert record is not None and record["sources"][-1]["path"] == str(child / "AGENTS.md")
    assert service.get_history(session)[0]["digest"] == snapshot.digest
    assert "CHILD instructions" not in str(session.export_metadata)

    specialist = runtime.orchestrator.pool.get_agent("engineer")
    prepared, _ = await specialist._prepare_stream_context()
    assert any("CHILD instructions" in (m.content or "") for m in prepared.api_messages)
    manager = runtime.orchestrator.subagents
    spawned = manager.spawn("Review", role="reviewer", system_prompt="Review only", tools=[])
    agent = manager._conversations[spawned.conversation_id].agent
    prepared, _ = await agent._prepare_stream_context()
    assert any("CHILD instructions" in (m.content or "") for m in prepared.api_messages)
    assert agent.instruction_context is not runtime.agent.instruction_context
    assert agent.system_prompt.startswith("Review only")
    sibling = root / "sibling"
    sibling.mkdir()
    (sibling / "AGENTS.md").write_text("SIBLING instructions", encoding="utf-8")
    agent.instruction_context.refresh(sibling)
    assert service.get(session)["sources"][-1]["path"] == str(sibling / "AGENTS.md")
    await runtime.agent._prepare_stream_context()
    assert service.get(session)["sources"][-1]["path"] == str(child / "AGENTS.md")
    # Persist only metadata, then restore under changed instructions. The next
    # request refreshes from disk and archives the earlier evidence.
    saved = sessions.save()
    (child / "AGENTS.md").write_text("UPDATED CHILD instructions", encoding="utf-8")
    restored = sessions.load(saved.stem)
    sessions.set_session(restored, runtime.orchestrator)
    prepared, _ = await runtime.agent._prepare_stream_context()
    assert any("UPDATED CHILD instructions" in (m.content or "") for m in prepared.api_messages)
    assert service.get(restored)["digest"] != record["digest"]
    assert record["digest"] in [item["digest"] for item in service.get_history(restored)]
    await manager.close()


@pytest.mark.asyncio
async def test_orchestrator_retries_scoped_writes_with_fresh_provider_requests(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    from collections.abc import AsyncIterator

    from henchman.agents.orchestrator_types import CompletionStatus
    from henchman.core.events import EventType

    monkeypatch.setattr(Path, "home", lambda: tmp_path / "home")
    root = tmp_path / "project"
    # Correlated writes now capture checkpoints, including Git's real ignore
    # policy. A marker-only .git directory is not a valid repository.
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    for name in ("left", "right"):
        (root / name).mkdir()
        (root / name / "AGENTS.md").write_text(f"{name.upper()} scoped rules", encoding="utf-8")
        (root / name / "file.txt").write_text("original", encoding="utf-8")
    monkeypatch.chdir(root)
    provider = MockProvider()
    requests = 0

    async def stream(messages: list[Message], **kwargs: Any) -> AsyncIterator[StreamChunk]:
        del kwargs
        nonlocal requests
        requests += 1
        if requests == 5:
            yield StreamChunk(content="Both files updated.", finish_reason=FinishReason.STOP)
            return
        name = "left" if requests <= 2 else "right"
        target = root / name / "file.txt"
        assert target.read_text() == "original"
        if requests in (2, 4):
            instructions = "\n".join(m.content or "" for m in messages if m.role == "system")
            assert f"{name.upper()} scoped rules" in instructions
            sibling = "RIGHT" if name == "left" else "LEFT"
            assert f"{sibling} scoped rules" not in instructions
        yield StreamChunk(
            tool_calls=[ToolCall(
                id=f"write-{requests}", name="write_file",
                arguments={"path": str(target), "content": "updated"},
            )],
            finish_reason=FinishReason.TOOL_CALLS,
        )

    monkeypatch.setattr(provider, "chat_completion_stream", stream)
    runtime = create_core_context(
        provider, auto_approve_tools=True,
        instruction_snapshot=ContextLoader(start_dir=root).load_snapshot(),
    )
    runtime.tool_manager.set_confirmation_handler()
    events = [event async for event in runtime.orchestrator.run("Update both files")]
    outcomes = [event.data["success"] for event in events if event.type == EventType.TOOL_CALL_RESULT]
    assert outcomes == [False, True, False, True], [
        event.data for event in events if event.type == EventType.TOOL_CALL_RESULT
    ]
    assert requests == 5
    assert runtime.orchestrator.last_completion_status == CompletionStatus.COMPLETED
    assert all((root / name / "file.txt").read_text() == "updated" for name in ("left", "right"))
    from henchman.advanced.checkpoints import CheckpointService

    checkpoints = CheckpointService(root)
    records = checkpoints.list_checkpoints()
    assert len(records) == 2
    assert {file.path for record in records for file in checkpoints.review(record.checkpoint_id).files} == {
        "left/file.txt", "right/file.txt",
    }
