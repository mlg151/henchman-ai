"""Conversation persistence across tool rounds, interruption, and compaction."""

import asyncio
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from henchman.agents.orchestrator import Orchestrator
from henchman.cli.session_manager import ReplSessionManager
from henchman.cli.textual_config import TextualConfig
from henchman.cli.textual_mixins import _InitMixin, _InputHandlerMixin
from henchman.core.agent import Agent
from henchman.core.session import SessionManager, SessionMessage
from henchman.providers.base import FinishReason, Message, ModelProvider, StreamChunk, ToolCall
from henchman.tools.base import Tool, ToolResult
from henchman.tools.registry import ToolRegistry


def make_manager(tmp_path: Path) -> ReplSessionManager:
    manager = ReplSessionManager(SessionManager(data_dir=tmp_path / ".henchman" / "sessions"))
    manager.set_session(manager.create_session("project"))
    return manager


def make_agent() -> Agent:
    return Agent(MagicMock(default_model="test-model"), system_prompt="current instructions")


def test_disk_roundtrip_preserves_two_tool_rounds_and_reasoning(tmp_path: Path) -> None:
    manager = make_manager(tmp_path)
    agent = make_agent()
    agent.turn.start_index = len(agent.messages)
    turn = [
        Message(role="user", content="fix and test"),
        Message(role="assistant", content="Inspecting", reasoning_content="Need evidence",
                tool_calls=[ToolCall("read", "read_file", {"path": "app.py"})]),
        Message(role="tool", tool_call_id="read", content="broken source"),
        Message(role="assistant", content="Checking", reasoning_content="Verify the change",
                tool_calls=[ToolCall("test", "shell", {"argv": ["pytest"]})]),
        Message(role="tool", tool_call_id="test", content="1 passed"),
        Message(role="assistant", content="Fixed and verified", reasoning_content="Done"),
    ]
    agent.messages.extend(turn)
    manager.sync_agent_turn(agent, session_start=0)
    manager.auto_save_session()
    restored = make_agent()
    manager.set_session(manager.load(manager.current.id), SimpleNamespace(tech_lead=restored))
    assert restored.messages == [Message(role="system", content="current instructions"), *turn]


def test_compaction_does_not_erase_persisted_older_turns(tmp_path: Path) -> None:
    manager = make_manager(tmp_path)
    manager.current.messages.extend([
        SessionMessage(role="user", content="older request"),
        SessionMessage(role="assistant", content="older answer"),
    ])
    start = len(manager.current.messages)
    manager.record_user_message("new request")
    manager.record_agent_message("incomplete UI event copy")
    agent = make_agent()
    agent.messages.append(Message(role="assistant", content="compacted context"))
    agent.turn.start_index = len(agent.messages)
    agent.messages.extend([
        Message(role="user", content="new request"),
        Message(role="assistant", content="authoritative answer"),
    ])
    manager.sync_agent_turn(agent, session_start=start)
    manager.sync_agent_turn(agent, session_start=start)
    manager.auto_save_session()
    loaded = manager.load(manager.current.id)
    assert [m.content for m in loaded.messages] == [
        "older request", "older answer", "new request", "authoritative answer",
    ]
    agent.messages[-1].content = "mutated later"
    assert manager.current.messages[-1].content == "authoritative answer"


class TwoRoundProvider(ModelProvider):
    name = "scripted"
    default_model = "test-model"

    def __init__(self, *, interrupt=False):
        self.rounds = 0
        self.interrupt = interrupt
        self.waiting = asyncio.Event()

    async def chat_completion_stream(self, messages, tools=None, **kwargs):
        self.rounds += 1
        if self.rounds <= 2:
            yield StreamChunk(thinking=f"reasoning {self.rounds}")
            yield StreamChunk(tool_calls=[ToolCall(str(self.rounds), "read_file", {})],
                              finish_reason=FinishReason.TOOL_CALLS)
        elif self.interrupt:
            yield StreamChunk(content="Partial answer", thinking="partial reasoning")
            self.waiting.set()
            await asyncio.Future()
        else:
            yield StreamChunk(content="Both checks passed.", finish_reason=FinishReason.STOP)


class EchoTool(Tool):
    name = "read_file"
    description = "Return controlled tool evidence."
    parameters = {"type": "object", "properties": {}}

    async def execute(self, **params):
        return ToolResult(content="Full persisted evidence")


class SessionApp(_InitMixin, _InputHandlerMixin):
    """Use production turn routing without a terminal driver or widget worker."""

    def __init__(self, manager, orchestrator, *, role=None):
        self.core_context = SimpleNamespace(session_manager=manager, orchestrator=orchestrator)
        self.config = TextualConfig(agent_role=role)
        self.posted = []

    def post_message(self, message):
        self.posted.append(message)


@pytest.mark.asyncio
@pytest.mark.parametrize("interrupt", [False, True])
@pytest.mark.parametrize("role", [None, "engineer"])
async def test_tui_turn_saves_full_tool_transcript_on_success_and_cancel(tmp_path, interrupt, role):
    manager = make_manager(tmp_path)
    provider = TwoRoundProvider(interrupt=interrupt)
    registry = ToolRegistry()
    registry.register(EchoTool())
    orchestrator = Orchestrator(provider, tool_registry=registry)
    app = SessionApp(manager, orchestrator, role=role)
    task = asyncio.create_task(app._run_orchestrator("Run both checks.", MagicMock()))
    if interrupt:
        await asyncio.wait_for(provider.waiting.wait(), timeout=5)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    else:
        await asyncio.wait_for(task, timeout=5)
    loaded = manager.load(manager.current.id)
    assert [m.role for m in loaded.messages[:6]] == [
        "user", "assistant", "tool", "assistant", "tool", "assistant",
    ]
    assert [m.tool_call_id for m in loaded.messages if m.role == "tool"] == ["1", "2"]
    assert [m.content for m in loaded.messages if m.role == "tool"] == [
        "Full persisted evidence", "Full persisted evidence",
    ]
    assert loaded.messages[1].reasoning_content == "reasoning 1"
    assert loaded.messages[3].reasoning_content == "reasoning 2"
    answer = [message for message in loaded.messages if message.role == "assistant"][-1]
    if interrupt:
        assert answer.content.startswith("Partial answer")
        assert "[Response interrupted.]" in answer.content
        assert answer.reasoning_content == "partial reasoning"
    else:
        assert answer.content == "Both checks passed."


def test_tui_initializes_session_without_overwriting_resumed_session(tmp_path):
    manager = ReplSessionManager(SessionManager(data_dir=tmp_path))
    app = SessionApp(manager, None)
    app._initialize_session()
    initial = manager.current
    assert initial is not None
    assert initial.project_hash == manager.compute_project_hash(Path.cwd())
    initial.tag = "resumed"
    app._initialize_session()
    assert manager.current is initial
    assert manager.current.tag == "resumed"


@pytest.mark.parametrize("role", [None, "engineer"])
def test_tui_resume_restores_selected_agent_and_reasoning(tmp_path, role):
    from henchman.cli.textual_mixins import _PublicAPIMixin

    manager = make_manager(tmp_path)
    manager.current.messages = [
        SessionMessage(role="user", content="earlier request"),
        SessionMessage(role="assistant", content="earlier answer", reasoning_content="reason"),
    ]
    manager.save()
    orchestrator = Orchestrator(TwoRoundProvider())
    app = SessionApp(manager, orchestrator, role=role)
    _PublicAPIMixin.set_session(app, manager.load(manager.current.id))
    selected = orchestrator.pool.get_agent(role) if role else orchestrator.tech_lead
    assert selected.messages[-2:] == [
        Message(role="user", content="earlier request"),
        Message(role="assistant", content="earlier answer", reasoning_content="reason"),
    ]
    if role:
        assert all(message.role == "system" for message in orchestrator.tech_lead.messages)


def test_tui_shutdown_saves_existing_session(tmp_path):
    from henchman.cli.textual_app import HenchmanTextualApp

    manager = make_manager(tmp_path)
    manager.record_user_message("persist at shutdown")
    app = SessionApp(manager, None)
    app._cleanup_confirm_futures = lambda: None
    HenchmanTextualApp.on_unmount(app)
    assert manager.load(manager.current.id).messages[0].content == "persist at shutdown"


@pytest.mark.asyncio
async def test_tui_cancel_during_tool_preserves_paired_calls_for_resume(tmp_path):
    class BlockingSecondRead(EchoTool):
        def __init__(self):
            self.calls = 0
            self.waiting = asyncio.Event()

        async def execute(self, **params):
            self.calls += 1
            if self.calls == 2:
                self.waiting.set()
                await asyncio.Future()
            return await super().execute(**params)

    manager = make_manager(tmp_path)
    registry = ToolRegistry()
    tool = BlockingSecondRead()
    registry.register(tool)
    orchestrator = Orchestrator(TwoRoundProvider(), tool_registry=registry)
    app = SessionApp(manager, orchestrator)
    task = asyncio.create_task(app._run_orchestrator("Run both checks.", MagicMock()))
    await asyncio.wait_for(tool.waiting.wait(), timeout=5)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    loaded = manager.load(manager.current.id)
    declared = [call["id"] for message in loaded.messages for call in (message.tool_calls or [])]
    results = [message for message in loaded.messages if message.role == "tool"]
    assert declared == ["1", "2"]
    assert [message.tool_call_id for message in results] == declared
    assert "cancel" in results[-1].content.lower()
    restored = make_agent()
    manager.set_session(loaded, history_agent=restored)
    assert restored.messages[-1].tool_call_id == "2"
    assert "cancel" in restored.messages[-1].content.lower()


@pytest.mark.parametrize("include_prompt", [False, True])
def test_resume_removes_prior_session_summary_and_keeps_configured_prompt(tmp_path, include_prompt):
    manager = make_manager(tmp_path)
    agent = make_agent()
    agent.messages.extend([
        Message(role="system", content="Summary of old private conversation"),
        Message(role="user", content="old request"),
    ])
    session = manager.create_session("project")
    if include_prompt:
        session.messages.append(SessionMessage(role="system", content="current instructions"))
    session.messages.extend([
        SessionMessage(role="system", content="Summary from selected session"),
        SessionMessage(role="user", content="selected request"),
    ])
    manager.set_session(session, history_agent=agent)
    manager.set_session(session, history_agent=agent)
    assert agent.messages == [
        Message(role="system", content="current instructions"),
        Message(role="system", content="Summary from selected session"),
        Message(role="user", content="selected request"),
    ]


@pytest.mark.asyncio
async def test_actual_same_turn_compaction_preserves_complete_tool_evidence_on_disk(tmp_path):
    evidence = "Evidence-line-12345678\n" * 1000
    assert len(evidence) == 23000

    class LargeEvidenceTool(EchoTool):
        async def execute(self, **params):
            return ToolResult(content=evidence)

    manager = make_manager(tmp_path)
    registry = ToolRegistry()
    registry.register(LargeEvidenceTool())
    orchestrator = Orchestrator(TwoRoundProvider(), tool_registry=registry)
    orchestrator.tech_lead = Agent(
        orchestrator.default_provider,
        tool_registry=registry,
        system_prompt="Keep working.",
        max_tokens=1000,
        intelligent_context=False,
        summarize_dropped=False,
    )
    app = SessionApp(manager, orchestrator)
    await app._run_orchestrator("Run both checks.", MagicMock())
    active_tools = [m for m in orchestrator.tech_lead.messages if m.role == "tool"]
    assert active_tools
    assert any(len(m.content) < len(evidence) for m in active_tools)
    loaded = manager.load(manager.current.id)
    saved_tools = [m for m in loaded.messages if m.role == "tool"]
    assert [m.tool_call_id for m in saved_tools] == ["1", "2"]
    assert [m.content for m in saved_tools] == [evidence, evidence]

    class ResumedProvider(ModelProvider):
        name = "resume-check"
        default_model = "test-model"
        checked = False

        async def chat_completion_stream(self, messages, tools=None, **kwargs):
            from henchman.utils.validation import validate_message_sequence

            validate_message_sequence(messages)
            assert [m.content for m in messages if m.role == "tool"] == [evidence, evidence]
            assert [m.reasoning_content for m in messages if m.tool_calls] == [
                "reasoning 1", "reasoning 2",
            ]
            assert messages[-1] == Message(role="user", content="Continue after resume.")
            self.checked = True
            yield StreamChunk(content="History verified.", finish_reason=FinishReason.STOP)

    resumed_provider = ResumedProvider()
    restored = Agent(resumed_provider, max_tokens=100000, summarize_dropped=False)
    manager.set_session(loaded, history_agent=restored)
    assert [m.content for m in restored.messages if m.role == "tool"] == [evidence, evidence]
    from henchman.core.events import EventType

    events = [event async for event in restored.run("Continue after resume.")]
    assert resumed_provider.checked
    assert not any(event.type == EventType.ERROR for event in events)
    assert restored.messages[-1].content == "History verified."
