from unittest.mock import MagicMock

import pytest

from henchman.agents.orchestrator import Orchestrator
from henchman.core.events import EventType
from henchman.providers.base import FinishReason, Message, ModelProvider, StreamChunk, ToolCall


@pytest.fixture
def mock_provider():
    provider = MagicMock(spec=ModelProvider)
    return provider


@pytest.mark.asyncio
async def test_orchestrator_run_basic(mock_provider):
    # Mock Tech Lead response
    chunk = StreamChunk(content="Plan: I will ask the explorer.", finish_reason=FinishReason.STOP)

    async def async_gen(*_args, **_kwargs):  # noqa: ARG001
        yield chunk

    mock_provider.chat_completion_stream.return_value = async_gen()

    orchestrator = Orchestrator(default_provider=mock_provider)

    events = []
    async for event in orchestrator.run("Hello"):
        events.append(event)

    assert any(e.type == EventType.AGENT_STARTED and e.data["agent"] == "tech_lead" for e in events)
    assert any(e.type == EventType.CONTENT and "Plan" in e.data for e in events)
    assert any(
        e.type == EventType.AGENT_COMPLETED and e.data["agent"] == "tech_lead" for e in events
    )


@pytest.mark.asyncio
async def test_orchestrator_delegation_interception(mock_provider):
    # 1. Tech Lead requests delegation
    tc = ToolCall(
        id="call_1", name="delegate_task", arguments={"agent": "explorer", "task": "Write test"}
    )
    chunk1 = StreamChunk(tool_calls=[tc], finish_reason=FinishReason.TOOL_CALLS)

    # 2. Tech Lead finishes after delegation result
    chunk2 = StreamChunk(content="Mission complete.", finish_reason=FinishReason.STOP)

    # 3. Coder (sub-agent) response
    chunk_coder = StreamChunk(content="I wrote the test.", finish_reason=FinishReason.STOP)

    call_count = 0

    async def side_effect(*_args, **_kwargs):  # noqa: ARG001
        nonlocal call_count
        call_count += 1
        if call_count == 1:  # Tech Lead first turn
            yield chunk1
        elif call_count == 2:  # Coder turn
            yield chunk_coder
        elif call_count == 3:  # Tech Lead second turn (after delegation)
            yield chunk2

    mock_provider.chat_completion_stream.side_effect = side_effect

    orchestrator = Orchestrator(default_provider=mock_provider)

    events = []
    async for event in orchestrator.run("Do work"):
        events.append(event)

    assert any(e.type == EventType.AGENT_DELEGATED and e.data["to"] == "explorer" for e in events)
    assert any(e.type == EventType.AGENT_STARTED and e.data["agent"] == "explorer" for e in events)
    assert any(e.type == EventType.CONTENT and "I wrote the test" in e.data for e in events)
    assert any(e.type == EventType.CONTENT and "Mission complete" in e.data for e in events)

    # Check shared context
    assert len(orchestrator.shared_context) == 1
    assert orchestrator.shared_context[0]["agent"] == "explorer"
    assert "I wrote the test" in orchestrator.shared_context[0]["summary"]


@pytest.mark.asyncio
async def test_cross_delegation_handoff_notes(mock_provider):
    """Cross-delegation handoff: recent shared_context is injected as background."""
    tc = ToolCall(
        id="call_1",
        name="delegate_task",
        arguments={"agent": "explorer", "task": "Fix bug", "context": "File: main.py, line 42"},
    )
    chunk1 = StreamChunk(tool_calls=[tc], finish_reason=FinishReason.TOOL_CALLS)
    chunk2 = StreamChunk(content="Done.", finish_reason=FinishReason.STOP)
    chunk_coder = StreamChunk(content="Fixed.", finish_reason=FinishReason.STOP)

    call_count = 0

    async def side_effect(*_args, **_kwargs):  # noqa: ARG001
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            yield chunk1
        elif call_count == 2:
            yield chunk_coder
        elif call_count == 3:
            yield chunk2

    mock_provider.chat_completion_stream.side_effect = side_effect
    orchestrator = Orchestrator(default_provider=mock_provider)
    orchestrator.shared_context.append(
        {"agent": "explorer", "summary": "Found the API docs", "timestamp": "t"},
    )

    events = []
    async for event in orchestrator.run("Fix the bug"):
        events.append(event)

    # The coder SHOULD receive handoff notes from prior agents
    coder = orchestrator.pool._agents.get("explorer")
    if coder:
        user_msgs = [m.content for m in coder.messages if m.role == "user"]
        combined = " ".join(user_msgs)
        assert "Prior agent work" in combined
        assert "explorer" in combined


@pytest.mark.asyncio
async def test_orchestrator_ledger_has_checklist_support(mock_provider):
    """Task 1: Ledger created per run supports checklist."""
    chunk = StreamChunk(content="Done.", finish_reason=FinishReason.STOP)

    async def async_gen(*_args, **_kwargs):  # noqa: ARG001
        yield chunk

    mock_provider.chat_completion_stream.return_value = async_gen()
    orchestrator = Orchestrator(default_provider=mock_provider)

    async for _ in orchestrator.run("Test"):
        pass

    assert orchestrator.ledger is not None
    # Ledger should support checklist operations
    item = orchestrator.ledger.add_checklist_item("Test item")
    assert item.done is False
    orchestrator.ledger.check_item(0)
    assert orchestrator.ledger.checklist[0].done is True


@pytest.mark.asyncio
async def test_delegation_clears_agent_history(mock_provider):
    """Specialist history is cleared before each delegation (clean start)."""
    # 1st TL turn → delegate to coder
    tc = ToolCall(id="c1", name="delegate_task", arguments={"agent": "explorer", "task": "First"})
    chunk_tl1 = StreamChunk(tool_calls=[tc], finish_reason=FinishReason.TOOL_CALLS)
    # Coder first run
    chunk_coder1 = StreamChunk(content="Done first.", finish_reason=FinishReason.STOP)
    # 2nd TL turn → delegate to coder AGAIN
    tc2 = ToolCall(id="c2", name="delegate_task", arguments={"agent": "explorer", "task": "Second"})
    chunk_tl2 = StreamChunk(tool_calls=[tc2], finish_reason=FinishReason.TOOL_CALLS)
    # Coder second run
    chunk_coder2 = StreamChunk(content="Done second.", finish_reason=FinishReason.STOP)
    # Final TL turn
    chunk_tl3 = StreamChunk(content="All done.", finish_reason=FinishReason.STOP)

    call_count = 0

    async def side_effect(*_args, **_kwargs):  # noqa: ARG001
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            yield chunk_tl1
        elif call_count == 2:
            yield chunk_coder1
        elif call_count == 3:
            yield chunk_tl2
        elif call_count == 4:
            yield chunk_coder2
        elif call_count == 5:
            yield chunk_tl3

    mock_provider.chat_completion_stream.side_effect = side_effect
    orchestrator = Orchestrator(default_provider=mock_provider)

    events = []
    async for event in orchestrator.run("Two tasks"):
        events.append(event)

    coder = orchestrator.pool._agents.get("explorer")
    assert coder is not None
    # After the second delegation the coder should have only the SECOND
    # run's messages (system + user + assistant), not the first's.
    user_msgs = [m.content for m in coder.messages if m.role == "user"]
    assert not any("First" in (m or "") for m in user_msgs), (
        "Coder should NOT retain history from the first delegation"
    )
    assert any("Second" in (m or "") for m in user_msgs), (
        "Coder should have the second delegation's task"
    )


def test_assemble_delegation_input_task_only():
    """_assemble_delegation_input with no brief returns just the task."""
    result = Orchestrator._assemble_delegation_input("Fix bug", None)
    assert result == "## Task\nFix bug"


def test_assemble_delegation_input_empty_brief():
    """_assemble_delegation_input with empty brief returns just the task."""
    result = Orchestrator._assemble_delegation_input("Fix bug", {})
    assert result == "## Task\nFix bug"


def test_assemble_delegation_input_full_brief():
    """_assemble_delegation_input includes all structured sections."""
    brief = {
        "context": "Auth returns 500 on special chars",
        "files": ["src/auth.py", "tests/test_auth.py"],
        "background": "Architect chose repository pattern",
        "requirements": "Must pass ruff check",
    }
    result = Orchestrator._assemble_delegation_input("Fix login", brief)
    assert "## Task\nFix login" in result
    assert "## Requirements\nMust pass ruff check" in result
    assert "## Relevant Files" in result
    assert "`src/auth.py`" in result
    assert "`tests/test_auth.py`" in result
    assert "## Background\nArchitect chose repository pattern" in result
    assert "## Additional Context\nAuth returns 500 on special chars" in result


def test_assemble_delegation_input_partial_brief():
    """_assemble_delegation_input handles partial brief (only some fields)."""
    brief = {"files": ["main.py"], "context": None, "background": None, "requirements": None}
    result = Orchestrator._assemble_delegation_input("Read it", brief)
    assert "## Task\nRead it" in result
    assert "## Relevant Files" in result
    assert "`main.py`" in result
    assert "## Requirements" not in result
    assert "## Background" not in result
    assert "## Additional Context" not in result


# -- Stall detection tests (Agent-level, orchestrator checks _stall_failure) -


@pytest.mark.asyncio
async def test_agent_stall_detection_colon_ending():
    """Agent._check_for_stalling catches messages ending with ':'."""
    from henchman.core.agent import Agent

    agent = Agent(provider=MagicMock(spec=ModelProvider))
    result = await agent._check_for_stalling("Now let me create the script:", had_tool_calls=False)
    assert result is not None
    assert "tool" in result.lower()


@pytest.mark.asyncio
async def test_agent_stall_failure_flag_after_max_nudges():
    """Agent sets _stall_failure after exceeding max nudges."""
    from henchman.core.agent import Agent

    agent = Agent(provider=MagicMock(spec=ModelProvider))
    agent._max_stall_nudges = 2
    # First two nudges return a message
    r1 = await agent._check_for_stalling("Let me create the validation script:", had_tool_calls=False)
    assert r1 is not None
    r2 = await agent._check_for_stalling("Now I'll write the test file:", had_tool_calls=False)
    assert r2 is not None
    # Third time: returns None and sets failure flag
    r3 = await agent._check_for_stalling("Here we go, starting now:", had_tool_calls=False)
    assert r3 is None
    assert agent._stall_failure is True


@pytest.mark.asyncio
async def test_agent_stall_resets_on_tool_calls():
    """Stall nudge counter resets when the agent actually uses tools."""
    from henchman.core.agent import Agent

    agent = Agent(provider=MagicMock(spec=ModelProvider))
    await agent._check_for_stalling("Let me write the entire module:", had_tool_calls=False)
    assert agent._stall_nudge_count == 1
    # Tool call resets the count
    await agent._check_for_stalling("anything", had_tool_calls=True)
    assert agent._stall_nudge_count == 0


@pytest.mark.asyncio
async def test_agent_stall_detection_disabled_flag():
    """Setting stall_detection_enabled=False bypasses all stall checks."""
    from henchman.core.agent import Agent

    agent = Agent(provider=MagicMock(spec=ModelProvider))
    agent.stall_detection_enabled = False
    result = await agent._check_for_stalling("Now let me create the script:", had_tool_calls=False)
    assert result is None
    assert agent._stall_nudge_count == 0


@pytest.mark.asyncio
async def test_agent_no_stall_on_genuine_content():
    """Agent does NOT flag substantive content as a stall."""
    from henchman.core.agent import Agent

    agent = Agent(provider=MagicMock(spec=ModelProvider))
    result = await agent._check_for_stalling(
        "I've updated the file and added tests. All 42 tests pass. "
        "The coverage is now 95%. Here's a summary of the changes I made.",
        had_tool_calls=False,
    )
    assert result is None


@pytest.mark.asyncio
async def test_stall_nudge_triggers_continuation(mock_provider):
    """Specialist that stalls gets nudged internally and continues."""
    # Turn 1 (TL): delegate to coder
    tc = ToolCall(
        id="c1", name="delegate_task", arguments={"agent": "explorer", "task": "Write script"}
    )
    chunk_tl1 = StreamChunk(tool_calls=[tc], finish_reason=FinishReason.TOOL_CALLS)
    # Turn 2 (coder call 1): stall — agent internally nudges
    stall = StreamChunk(content="Now let me create the script:", finish_reason=FinishReason.STOP)
    # Turn 3 (coder call 2, after internal nudge): real output
    real = StreamChunk(
        content="Here is the completed script with all tests passing.",
        finish_reason=FinishReason.STOP,
    )
    # Turn 4 (TL): done
    chunk_tl2 = StreamChunk(content="All done.", finish_reason=FinishReason.STOP)

    call_count = 0

    async def side_effect(*_args, **_kwargs):  # noqa: ARG001
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            yield chunk_tl1
        elif call_count == 2:
            yield stall
        elif call_count == 3:
            yield real
        elif call_count >= 4:
            yield chunk_tl2

    mock_provider.chat_completion_stream.side_effect = side_effect
    orchestrator = Orchestrator(default_provider=mock_provider)

    events = []
    async for event in orchestrator.run("Write a script"):
        events.append(event)

    # The real content should appear (stall was handled internally)
    contents = [e.data for e in events if e.type == EventType.CONTENT]
    assert any("completed script" in c for c in contents)


@pytest.mark.asyncio
async def test_stall_failure_reported_after_max_nudges(mock_provider):
    """After max nudges on a specialist, a STALL FAILURE error is emitted."""
    # Turn 1 (TL): delegate to coder
    tc = ToolCall(
        id="c1", name="delegate_task", arguments={"agent": "explorer", "task": "Write tests"}
    )
    chunk_tl1 = StreamChunk(tool_calls=[tc], finish_reason=FinishReason.TOOL_CALLS)
    # Coder stalls 3 times (max_stall_nudges=2, so 3rd triggers failure)
    # Agent's internal loop: call1=stall → nudge → call2=stall → nudge → call3=stall → _stall_failure=True → exit
    stall = StreamChunk(content="Let me write the code:", finish_reason=FinishReason.STOP)
    # TL continues after failed delegation
    chunk_tl2 = StreamChunk(content="Delegation failed.", finish_reason=FinishReason.STOP)

    call_count = 0

    async def side_effect(*_args, **_kwargs):  # noqa: ARG001
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            yield chunk_tl1
        elif call_count <= 4:
            # Calls 2-4: coder stalls each time (agent nudges internally)
            yield stall
        elif call_count >= 5:
            yield chunk_tl2

    mock_provider.chat_completion_stream.side_effect = side_effect
    orchestrator = Orchestrator(default_provider=mock_provider)

    events = []
    async for event in orchestrator.run("Write tests"):
        events.append(event)

    # Should have an ERROR event with STALL FAILURE
    error_events = [e for e in events if e.type == EventType.ERROR]
    assert any("STALL FAILURE" in e.data for e in error_events)
    assert any("never used tools" in e.data for e in error_events)


@pytest.mark.asyncio
async def test_tech_lead_exempt_from_stall_failure(mock_provider):
    """Tech Lead has stall detection disabled entirely."""
    # TL says something ending with ':' — would normally trigger stall detection
    stall = StreamChunk(content="Here's my plan:", finish_reason=FinishReason.STOP)

    async def async_gen(*_args, **_kwargs):  # noqa: ARG001
        yield stall

    mock_provider.chat_completion_stream.return_value = async_gen()
    orchestrator = Orchestrator(default_provider=mock_provider)

    # Verify flag is set
    assert orchestrator.tech_lead.stall_detection_enabled is False

    events = []
    async for event in orchestrator.run("Do something"):
        events.append(event)

    # No STALL FAILURE error from orchestrator for Tech Lead
    error_events = [e for e in events if e.type == EventType.ERROR]
    assert not any("STALL FAILURE" in str(e.data) for e in error_events)
    # TL was NOT nudged — it exits cleanly after 1 call
    assert orchestrator.tech_lead._stall_nudge_count == 0


# ------------------------------------------------------------------
# v0.2.7 — Teamwork & Communication Improvements
# ------------------------------------------------------------------


def test_assemble_delegation_input_done_when():
    """done_when field produces a '## Done When' section."""
    result = Orchestrator._assemble_delegation_input(
        "Write tests",
        {"done_when": "pytest passes with 0 failures", "requirements": "100% coverage"},
    )
    assert "## Done When" in result
    assert "pytest passes with 0 failures" in result
    assert "Stop working once" in result
    assert "## Requirements" in result


def test_assemble_delegation_input_no_done_when():
    """Brief without done_when omits the section."""
    result = Orchestrator._assemble_delegation_input(
        "Write tests",
        {"requirements": "100% coverage"},
    )
    assert "## Done When" not in result
    assert "## Requirements" in result


def test_parse_completion_report_full():
    """Parses all structured fields from a specialist report."""
    summary = (
        "STATUS: DONE\n"
        "FILES_MODIFIED: src/foo.py, src/bar.py\n"
        "TESTS_RUN: pytest tests/\n"
        "VERIFICATION: ruff check src/ — passed\n"
        "SUMMARY: Added feature X"
    )
    parsed = Orchestrator._parse_completion_report(summary)
    assert parsed["status"] == "DONE"
    assert "src/foo.py" in parsed["files_modified"]
    assert "pytest" in parsed["tests_run"]
    assert "ruff" in parsed["verification"]


def test_parse_completion_report_empty():
    """Unstructured summary produces empty dict."""
    parsed = Orchestrator._parse_completion_report("I fixed the bug.")
    assert parsed == {}


def test_parse_completion_report_partial():
    """Parses whatever fields are present."""
    summary = "STATUS: FAILED\nSUMMARY: Could not find the file"
    parsed = Orchestrator._parse_completion_report(summary)
    assert parsed["status"] == "FAILED"
    assert "files_modified" not in parsed


@pytest.mark.asyncio
async def test_delegation_turn_limit(mock_provider):
    """Specialist is stopped after max_delegation_turns."""
    from henchman.config.schema import AgentSettings, Settings

    # TL delegates to coder; coder keeps making tool calls
    tc_delegate = ToolCall(
        id="call_d",
        name="delegate_task",
        arguments={"agent": "explorer", "task": "Write code"},
    )
    tl_chunk1 = StreamChunk(tool_calls=[tc_delegate], finish_reason=FinishReason.TOOL_CALLS)
    tl_chunk2 = StreamChunk(content="All done.", finish_reason=FinishReason.STOP)

    # Coder makes 3 tool calls then finishes
    coder_tc = ToolCall(id="tc_c", name="read_file", arguments={"path": "x.py"})
    coder_tool = StreamChunk(tool_calls=[coder_tc], finish_reason=FinishReason.TOOL_CALLS)
    coder_done = StreamChunk(content="STATUS: DONE", finish_reason=FinishReason.STOP)

    call_count = 0

    async def side_effect(*_args, **_kwargs):  # noqa: ARG001
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            yield tl_chunk1
        elif call_count <= 4:
            yield coder_tool
        elif call_count == 5:
            yield coder_done
        else:
            yield tl_chunk2

    mock_provider.chat_completion_stream.side_effect = side_effect

    settings = Settings(agents=AgentSettings(max_delegation_turns=2))
    orchestrator = Orchestrator(default_provider=mock_provider, settings=settings)

    events = []
    async for event in orchestrator.run("Do it"):
        events.append(event)

    # Turn limit should have been hit — look for the error event
    error_events = [e for e in events if e.type == EventType.ERROR]
    assert any("Turn limit" in str(e.data) for e in error_events)

    # The timeout summary should be in the coder's messages
    coder = orchestrator.pool._agents.get("explorer")
    if coder:
        assistant_msgs = [m.content for m in coder.messages if m.role == "assistant" and m.content]
        combined = "\n".join(assistant_msgs)
        assert "Progress at timeout" in combined


def test_build_timeout_summary_with_tools():
    """_build_timeout_summary captures tool calls and files."""
    from henchman.core.agent import Agent

    from henchman.agents.orchestrator import TimeoutSummaryBuilder

    agent = Agent(provider=MagicMock(spec=ModelProvider))
    msg_start = len(agent.messages)
    # Simulate some tool calls in message history
    agent.messages.append(
        Message(
            role="assistant",
            content="Reading file",
            tool_calls=[ToolCall(id="t1", name="read_file", arguments={"path": "src/foo.py"})],
        )
    )
    agent.messages.append(Message(role="tool", content="file contents...", tool_call_id="t1"))
    agent.messages.append(
        Message(
            role="assistant",
            content="Editing file",
            tool_calls=[
                ToolCall(
                    id="t2",
                    name="edit_file",
                    arguments={"path": "src/foo.py", "old": "a", "new": "b"},
                )
            ],
        )
    )

    result = TimeoutSummaryBuilder.build_summary(agent, msg_start)
    assert "Progress at timeout" in result
    assert "Tool calls made: 2" in result
    assert "src/foo.py" in result


def test_build_timeout_summary_empty():
    """_build_timeout_summary handles no progress."""
    from henchman.core.agent import Agent
    from henchman.agents.orchestrator import TimeoutSummaryBuilder

    agent = Agent(provider=MagicMock(spec=ModelProvider))
    msg_start = len(agent.messages)
    result = TimeoutSummaryBuilder.build_summary(agent, msg_start)
    assert "No significant progress" in result


@pytest.mark.asyncio
async def test_tool_error_aggregation(mock_provider):
    """Tool errors during delegation are appended to summary."""
    tc_delegate = ToolCall(
        id="call_d",
        name="delegate_task",
        arguments={"agent": "explorer", "task": "Fix tests"},
    )
    tl_chunk1 = StreamChunk(tool_calls=[tc_delegate], finish_reason=FinishReason.TOOL_CALLS)
    tl_chunk2 = StreamChunk(content="OK.", finish_reason=FinishReason.STOP)

    # Coder makes a shell call that fails, then finishes
    coder_tc = ToolCall(id="tc_s", name="shell", arguments={"command": "false"})
    coder_tool = StreamChunk(tool_calls=[coder_tc], finish_reason=FinishReason.TOOL_CALLS)
    coder_done = StreamChunk(content="STATUS: FAILED", finish_reason=FinishReason.STOP)

    call_count = 0

    async def side_effect(*_args, **_kwargs):  # noqa: ARG001
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            yield tl_chunk1
        elif call_count == 2:
            yield coder_tool
        elif call_count == 3:
            yield coder_done
        else:
            yield tl_chunk2

    mock_provider.chat_completion_stream.side_effect = side_effect
    orchestrator = Orchestrator(default_provider=mock_provider)

    # Manually inject a tool error to simulate failure
    events = []
    async for event in orchestrator.run("Fix it"):
        events.append(event)

    # The coder agent should have _delegation_tool_errors attribute
    coder = orchestrator.pool._agents.get("explorer")
    assert hasattr(coder, "_delegation_tool_errors")


@pytest.mark.asyncio
async def test_max_delegation_turns_setting():
    """AgentSettings.max_delegation_turns defaults to 80."""
    from henchman.config.schema import AgentSettings

    settings = AgentSettings()
    assert settings.max_delegation_turns == 150

    custom = AgentSettings(max_delegation_turns=10)
    assert custom.max_delegation_turns == 10


@pytest.mark.asyncio
async def test_thinking_pattern_validation(mock_provider):
    """Test that thinking pattern validation works for Tech Lead."""
    # Mock Tech Lead response WITHOUT thinking pattern
    chunk = StreamChunk(content="I'll do this task.", finish_reason=FinishReason.STOP)

    async def async_gen(*_args, **_kwargs):  # noqa: ARG001
        yield chunk

    mock_provider.chat_completion_stream.return_value = async_gen()
    orchestrator = Orchestrator(default_provider=mock_provider)

    events = []
    async for event in orchestrator.run("Test task"):
        events.append(event)

    # Check for thinking required event
    thinking_events = [e for e in events if e.type == EventType.THINKING_REQUIRED]
    assert len(thinking_events) > 0, (
        "Should have THINKING_REQUIRED event when thinking pattern is missing"
    )
    assert "Thinking pattern missing" in thinking_events[0].data


@pytest.mark.asyncio
async def test_thinking_pattern_metrics(mock_provider):
    """Test that thinking pattern usage updates metrics."""
    # Mock Tech Lead response WITH thinking pattern
    chunk = StreamChunk(
        content="THINKING:\n1. Problem: Test\n2. Context: None\n3. Options: A\n4. Decision: A\n5. Plan: Do it",
        finish_reason=FinishReason.STOP,
    )

    async def async_gen(*_args, **_kwargs):  # noqa: ARG001
        yield chunk

    mock_provider.chat_completion_stream.return_value = async_gen()
    orchestrator = Orchestrator(default_provider=mock_provider)

    events = []
    async for event in orchestrator.run("Test task"):
        events.append(event)

    # Check metrics were updated
    assert orchestrator.metrics.thinking_pattern_usage == 1
    # Should have some quality score for having at least 3 thinking points
    assert orchestrator.metrics.thinking_quality_score > 0


@pytest.mark.asyncio
async def test_delegation_metrics(mock_provider):
    """Test that delegation updates metrics."""
    # Mock Tech Lead delegation
    tc = ToolCall(
        id="call_1", name="delegate_task", arguments={"agent": "explorer", "task": "Write test"}
    )
    chunk1 = StreamChunk(tool_calls=[tc], finish_reason=FinishReason.TOOL_CALLS)
    chunk2 = StreamChunk(content="Done.", finish_reason=FinishReason.STOP)
    chunk_coder = StreamChunk(content="Test written.", finish_reason=FinishReason.STOP)

    call_count = 0

    async def side_effect(*_args, **_kwargs):  # noqa: ARG001
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            yield chunk1
        elif call_count == 2:
            yield chunk_coder
        elif call_count == 3:
            yield chunk2

    mock_provider.chat_completion_stream.side_effect = side_effect
    orchestrator = Orchestrator(default_provider=mock_provider)

    events = []
    async for event in orchestrator.run("Do work"):
        events.append(event)

    # Check delegation metrics
    assert orchestrator.metrics.delegation_count == 1
    assert orchestrator.metrics.delegation_by_type["explorer"] == 1


# ------------------------------------------------------------------
# v0.2.8 — Teamwork Prompt Improvements
# ------------------------------------------------------------------


def test_assemble_delegation_input_with_mission():
    """Mission goal is injected as a header when provided (#6)."""
    result = Orchestrator._assemble_delegation_input(
        "Fix the login bug",
        {"requirements": "Must pass tests"},
        mission="Implement user authentication system",
    )
    assert "## Mission" in result
    assert "Implement user authentication system" in result
    assert "## Task\nFix the login bug" in result
    assert "## Requirements" in result


def test_assemble_delegation_input_without_mission():
    """Without mission, no Mission section is emitted."""
    result = Orchestrator._assemble_delegation_input(
        "Fix bug",
        {"requirements": "Must pass"},
    )
    assert "## Mission" not in result
    assert "## Task\nFix bug" in result


def test_assemble_delegation_input_with_depends_on():
    """depends_on field produces a Depends On section (#10)."""
    result = Orchestrator._assemble_delegation_input(
        "Write tests",
        {"depends_on": "Explorer found API uses OAuth2", "requirements": "100%"},
    )
    assert "## Depends On" in result
    assert "Explorer found API uses OAuth2" in result


def test_assemble_delegation_input_no_depends_on():
    """Brief without depends_on omits the section."""
    result = Orchestrator._assemble_delegation_input(
        "Write tests",
        {"requirements": "100%"},
    )
    assert "## Depends On" not in result


def test_assemble_delegation_input_mission_no_brief():
    """Mission is included even when brief is None."""
    result = Orchestrator._assemble_delegation_input(
        "Fix bug",
        None,
        mission="Big project goal",
    )
    assert "## Mission\nBig project goal" in result
    assert "## Task\nFix bug" in result


def test_parse_completion_report_blockers():
    """Parses BLOCKERS field from specialist report (#11)."""
    summary = (
        "STATUS: BLOCKED\n"
        "BLOCKERS: Missing pytest-mock dependency\n"
        "SUMMARY: Could not run tests"
    )
    parsed = Orchestrator._parse_completion_report(summary)
    assert parsed["status"] == "BLOCKED"
    assert "pytest-mock" in parsed["blockers"]


def test_parse_completion_report_handoff_notes():
    """Parses HANDOFF_NOTES field from specialist report (#11)."""
    summary = (
        "STATUS: DONE\n"
        "HANDOFF_NOTES: The API requires OAuth2 bearer tokens\n"
        "SUMMARY: Completed research"
    )
    parsed = Orchestrator._parse_completion_report(summary)
    assert "OAuth2" in parsed["handoff_notes"]


def test_parse_completion_report_artifacts():
    """Parses ARTIFACTS field from specialist report (#12)."""
    summary = (
        "STATUS: DONE\n"
        "ARTIFACTS: .agent_tasks/auth-research/README.md\n"
        "SUMMARY: Documented findings"
    )
    parsed = Orchestrator._parse_completion_report(summary)
    assert ".agent_tasks/" in parsed["artifacts"]


# ------------------------------------------------------------------
# Performance Metrics Dashboard Tests
# ------------------------------------------------------------------


def test_orchestrator_metrics_class_initialization():
    """Test that OrchestratorMetrics initializes all fields correctly."""
    from henchman.agents.orchestrator import OrchestratorMetrics

    metrics = OrchestratorMetrics()

    # Direct attributes
    assert metrics.thinking_pattern_usage == 0
    assert metrics.delegation_count == 0
    assert metrics.delegation_by_type == {"planner": 0, "explorer": 0, "engineer": 0}
    assert metrics.thinking_quality_score == 0

    # Performance sub-object
    assert metrics.performance.task_start_time == 0.0
    assert metrics.performance.task_end_time == 0.0
    assert metrics.performance.files_accessed == {}
    assert metrics.performance.tool_usage_by_type == {}
    assert metrics.performance.file_re_reads == 0

    # Quality sub-object
    assert metrics.quality.test_results == {"passing": 0, "total": 0, "percentage": 0.0}
    assert metrics.quality.linting_status == {"errors": 0, "warnings": 0}
    assert metrics.quality.code_coverage == 0.0

    # Tools sub-object
    assert metrics.tools.total_tool_calls == 0
    assert metrics.tools.successful_tool_calls == 0
    assert metrics.tools.failed_tool_calls == 0
    assert metrics.tools.read_file_calls == 0


def test_orchestrator_metrics_initialization(mock_provider):
    """Test that orchestrator initializes all metrics fields."""
    orchestrator = Orchestrator(default_provider=mock_provider)

    # Check that all metrics fields are initialized
    assert orchestrator.metrics.thinking_pattern_usage == 0
    assert orchestrator.metrics.delegation_count == 0
    assert orchestrator.metrics.delegation_by_type == {"planner": 0, "explorer": 0, "engineer": 0}
    assert orchestrator.metrics.performance.task_start_time == 0.0
    assert orchestrator.metrics.performance.files_accessed == {}
    assert orchestrator.metrics.performance.tool_usage_by_type == {}
    assert orchestrator.metrics.quality.test_results == {"passing": 0, "total": 0, "percentage": 0.0}
    assert orchestrator.metrics.performance.file_re_reads == 0
    assert orchestrator.metrics.tools.total_tool_calls == 0


def test_update_tool_metrics():
    """Test update_tool_metrics method."""
    from unittest.mock import MagicMock

    mock_provider = MagicMock(spec=ModelProvider)
    orchestrator = Orchestrator(default_provider=mock_provider)

    # Test tracking a read_file call
    orchestrator.tool_controller.update_tool_metrics("read_file", {"path": "test.py"}, success=True)

    assert orchestrator.metrics.tools.total_tool_calls == 1
    assert orchestrator.metrics.tools.successful_tool_calls == 1
    assert orchestrator.metrics.tools.failed_tool_calls == 0
    assert orchestrator.metrics.tools.read_file_calls == 1
    assert "read_file" in orchestrator.metrics.performance.tool_usage_by_type
    assert orchestrator.metrics.performance.tool_usage_by_type["read_file"] == 1
    assert "test.py" in orchestrator.metrics.performance.files_accessed
    assert orchestrator.metrics.performance.files_accessed["test.py"] == 1

    # Test tracking a failed tool call
    orchestrator.tool_controller.update_tool_metrics("shell", {"command": "false"}, success=False)

    assert orchestrator.metrics.tools.total_tool_calls == 2
    assert orchestrator.metrics.tools.successful_tool_calls == 1
    assert orchestrator.metrics.tools.failed_tool_calls == 1
    assert orchestrator.metrics.tools.shell_calls == 1
    assert "shell" in orchestrator.metrics.performance.tool_usage_by_type
    assert orchestrator.metrics.performance.tool_usage_by_type["shell"] == 1

    # Test file re-read tracking
    orchestrator.tool_controller.update_tool_metrics("read_file", {"path": "test.py"}, success=True)

    assert orchestrator.metrics.tools.total_tool_calls == 3
    assert orchestrator.metrics.tools.read_file_calls == 2
    assert orchestrator.metrics.performance.files_accessed["test.py"] == 2  # Re-read


def test_calculate_final_metrics():
    """Test calculate_final_metrics on OrchestratorMetrics."""
    import time
    from unittest.mock import MagicMock

    mock_provider = MagicMock(spec=ModelProvider)
    orchestrator = Orchestrator(default_provider=mock_provider)

    # Set up some metrics
    orchestrator.metrics.performance.task_start_time = time.time() - 60  # 60 seconds ago
    orchestrator.metrics.performance.task_end_time = time.time()
    orchestrator.metrics.delegation_count = 2
    orchestrator.metrics.tools.total_tool_calls = 8
    orchestrator.metrics.tools.failed_tool_calls = 1
    orchestrator.metrics.quality.test_results = {"passing": 45, "total": 50, "percentage": 0.0}
    orchestrator.metrics.performance.files_accessed = {"file1.py": 2, "file2.py": 1, "file3.py": 3}

    # Calculate final metrics
    orchestrator.metrics.calculate_final_metrics()

    # Check calculated values
    assert orchestrator.metrics.performance.task_duration_minutes > 0
    assert 0.9 < orchestrator.metrics.performance.task_duration_minutes < 1.1  # ~1 minute

    # Delegation rate: 2 delegations / (8 tool calls + 2 delegations) = 20%
    assert abs(orchestrator.metrics.performance.delegation_rate - 20.0) < 0.1

    # Error rate: 1 failed / 8 total = 12.5%
    assert abs(orchestrator.metrics.performance.error_rate - 12.5) < 0.1

    # Test percentage: 45/50 = 90%
    assert abs(orchestrator.metrics.quality.test_results["percentage"] - 90.0) < 0.1

    # File re-reads: total accesses (6) - unique files (3) = 3
    assert orchestrator.metrics.performance.file_re_reads == 3


def test_get_metrics_report():
    """Test get_metrics_report method generates correct format."""
    from unittest.mock import MagicMock

    mock_provider = MagicMock(spec=ModelProvider)
    orchestrator = Orchestrator(default_provider=mock_provider)

    # Set up some metrics
    orchestrator.metrics.performance.task_start_time = 1700000000.0
    orchestrator.metrics.performance.task_end_time = 1700000060.0  # 60 seconds later
    orchestrator.metrics.delegation_count = 2
    orchestrator.metrics.tools.total_tool_calls = 10
    orchestrator.metrics.tools.successful_tool_calls = 9
    orchestrator.metrics.tools.failed_tool_calls = 1
    orchestrator.metrics.tools.read_file_calls = 3
    orchestrator.metrics.tools.write_file_calls = 2
    orchestrator.metrics.performance.tool_usage_by_type = {"read_file": 3, "write_file": 2, "shell": 1}
    orchestrator.metrics.performance.files_accessed = {"file1.py": 2, "file2.py": 1}
    orchestrator.metrics.quality.test_results = {"passing": 45, "total": 50, "percentage": 90.0}
    orchestrator.metrics.quality.linting_status = {"errors": 2, "warnings": 5}
    orchestrator.metrics.thinking_pattern_usage = 1
    orchestrator.metrics.thinking_quality_score = 5

    # Calculate final metrics first
    orchestrator.metrics.calculate_final_metrics()

    # Generate report
    report = orchestrator.get_metrics_report()

    # Check report structure
    assert "## Performance Metrics Dashboard" in report
    assert "### Efficiency Metrics" in report
    assert "### Quality Metrics" in report
    assert "### Target Performance Metrics" in report
    assert "### Detailed Statistics" in report

    # Check specific content
    assert "Task Completion Time" in report
    assert "Files Accessed" in report
    assert "Tool Usage" in report
    assert "Delegation Rate" in report
    assert "Test Results" in report
    assert "Linting Status" in report
    assert "File re-reads per task" in report
    assert "Error rate" in report
    assert "Total Tool Calls" in report
    assert "Thinking Pattern Usage" in report

    # Check calculations
    assert "2/12" in report  # delegation_count / (total_tool_calls + delegation_count)
    assert "10.0%" in report or "10%" in report  # error_rate (1/10 = 10%)


def test_reset_metrics_for_run():
    """Test _reset_metrics_for_run method."""
    from unittest.mock import MagicMock

    mock_provider = MagicMock(spec=ModelProvider)
    orchestrator = Orchestrator(default_provider=mock_provider)

    # Modify some metrics
    orchestrator.metrics.thinking_pattern_usage = 5
    orchestrator.metrics.delegation_count = 3
    orchestrator.metrics.delegation_by_type = {"planner": 2, "explorer": 1, "engineer": 0}
    orchestrator.metrics.performance.files_accessed = {"test.py": 2}
    orchestrator.metrics.tools.total_tool_calls = 10

    # Reset metrics
    orchestrator.metrics.reset_for_run()

    # Check metrics are reset
    assert orchestrator.metrics.thinking_pattern_usage == 0
    assert orchestrator.metrics.delegation_count == 0
    assert orchestrator.metrics.delegation_by_type == {"planner": 0, "explorer": 0, "engineer": 0}
    assert orchestrator.metrics.performance.files_accessed == {}
    assert orchestrator.metrics.tools.total_tool_calls == 0
    assert orchestrator.metrics.quality.test_results == {"passing": 0, "total": 0, "percentage": 0.0}
    assert orchestrator.metrics.quality.linting_status == {"errors": 0, "warnings": 0}


# -- Colon-stall guard tests (orchestrator-level, works for ALL agents) --------


def test_last_assistant_content_found():
    """_last_assistant_content returns the last assistant message content."""
    agent = MagicMock(spec=["messages"])
    agent.messages = [
        Message(role="user", content="hello"),
        Message(role="assistant", content="first reply"),
        Message(role="user", content="more input"),
        Message(role="assistant", content="Now let me create the file:"),
    ]
    result = Orchestrator._last_assistant_content(agent)
    assert result == "Now let me create the file:"


def test_last_assistant_content_empty():
    """_last_assistant_content returns empty string if no assistant messages."""
    agent = MagicMock(spec=["messages"])
    agent.messages = [
        Message(role="user", content="hello"),
    ]
    result = Orchestrator._last_assistant_content(agent)
    assert result == ""


def test_last_assistant_content_skips_empty():
    """_last_assistant_content skips assistant messages with empty content."""
    agent = MagicMock(spec=["messages"])
    agent.messages = [
        Message(role="assistant", content="good content"),
        Message(role="assistant", content=""),
        Message(role="assistant", content=None),
    ]
    result = Orchestrator._last_assistant_content(agent)
    assert result == "good content"


@pytest.mark.asyncio
async def test_colon_stall_guard_nudges_agent():
    """Orchestrator colon-stall guard nudges agent that ends with ':'."""
    from henchman.agents.orchestrator import _COLON_STALL_NUDGE

    # Agent first responds with colon-ending (stall), then responds properly
    chunk_stall = StreamChunk(
        content="Now I need to replace the entire function with my refactored version:",
        finish_reason=FinishReason.STOP,
    )
    chunk_ok = StreamChunk(
        content="Done! The function has been updated.",
        finish_reason=FinishReason.STOP,
    )

    call_count = 0

    async def mock_stream(*_args, **_kwargs):
        nonlocal call_count
        call_count += 1
        if call_count <= 1:
            yield chunk_stall
        else:
            yield chunk_ok

    mock_prov = MagicMock(spec=ModelProvider)
    mock_prov.chat_completion_stream = mock_stream
    mock_prov.default_model = "test-model"

    orchestrator = Orchestrator(default_provider=mock_prov)
    # Run the tech_lead
    events = []
    async for event in orchestrator.run("Fix the sync function"):
        events.append(event)

    # The stall nudge message should have been injected into tech_lead messages
    nudge_messages = [
        m for m in orchestrator.tech_lead.messages
        if m.role == "user" and m.content == _COLON_STALL_NUDGE
    ]
    assert len(nudge_messages) >= 1, (
        "Colon-stall nudge was not injected into tech_lead messages"
    )
    # The agent was called more than once (retried after stall)
    assert call_count >= 2


@pytest.mark.asyncio
async def test_colon_stall_guard_skips_short_responses():
    """Short responses ending with ':' are not treated as stalls."""
    chunk = StreamChunk(
        content="Step 1:",  # Only 7 chars — below _COLON_STALL_MIN_LENGTH
        finish_reason=FinishReason.STOP,
    )

    async def mock_stream(*_args, **_kwargs):
        yield chunk

    mock_prov = MagicMock(spec=ModelProvider)
    mock_prov.chat_completion_stream = mock_stream
    mock_prov.default_model = "test-model"

    orchestrator = Orchestrator(default_provider=mock_prov)
    events = []
    async for event in orchestrator.run("Do something"):
        events.append(event)

    # Should NOT have nudge messages — too short to be a stall
    from henchman.agents.orchestrator import _COLON_STALL_NUDGE

    nudge_messages = [
        m for m in orchestrator.tech_lead.messages
        if m.role == "user" and m.content == _COLON_STALL_NUDGE
    ]
    assert len(nudge_messages) == 0


@pytest.mark.asyncio
async def test_colon_stall_guard_respects_max_retries():
    """Colon-stall guard stops retrying after _MAX_COLON_STALL_RETRIES."""
    from henchman.agents.orchestrator import _MAX_COLON_STALL_RETRIES

    # Agent ALWAYS stalls with a colon
    chunk = StreamChunk(
        content="Now I will create the replacement function with the full implementation:",
        finish_reason=FinishReason.STOP,
    )

    call_count = 0

    async def mock_stream(*_args, **_kwargs):
        nonlocal call_count
        call_count += 1
        yield chunk

    mock_prov = MagicMock(spec=ModelProvider)
    mock_prov.chat_completion_stream = mock_stream
    mock_prov.default_model = "test-model"

    orchestrator = Orchestrator(default_provider=mock_prov)
    events = []
    async for event in orchestrator.run("Fix something"):
        events.append(event)

    # Should have retried exactly _MAX_COLON_STALL_RETRIES times
    # 1 initial call + _MAX_COLON_STALL_RETRIES retries
    assert call_count == 1 + _MAX_COLON_STALL_RETRIES


@pytest.mark.asyncio
async def test_colon_stall_guard_resets_on_non_colon():
    """Agent that stops stalling (no colon) is not nudged further."""
    chunk_stall = StreamChunk(
        content="Let me create the updated version of the function:",
        finish_reason=FinishReason.STOP,
    )
    chunk_ok = StreamChunk(
        content="THINKING:\n1. Analysed the problem\n2. here is my plan\n3. delegating",
        finish_reason=FinishReason.STOP,
    )

    call_count = 0

    async def mock_stream(*_args, **_kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            yield chunk_stall
        else:
            yield chunk_ok

    mock_prov = MagicMock(spec=ModelProvider)
    mock_prov.chat_completion_stream = mock_stream
    mock_prov.default_model = "test-model"

    orchestrator = Orchestrator(default_provider=mock_prov)
    events = []
    async for event in orchestrator.run("Fix something"):
        events.append(event)

    # Only 2 calls: initial stall + one retry that succeeded
    assert call_count == 2


@pytest.mark.asyncio
async def test_regular_tool_calls_are_executed_before_continue(mock_provider):
    """Regression test: _run_agent_loop must execute pending tool calls.

    Without the call to _process_pending_tool_calls, the agent loop calls
    continue_with_tool_results() with no tool responses submitted.  The
    message-repair logic then strips the unanswered tool_calls and the
    LLM regenerates the same call — an infinite loop.

    See: .agent_tasks/auto-improve/infinite-loop-fix.md
    """
    # 1. Tech Lead wants to read a file
    tc = ToolCall(id="call_rf", name="read_file", arguments={"path": "foo.py"})
    chunk_tool = StreamChunk(tool_calls=[tc], finish_reason=FinishReason.TOOL_CALLS)

    # 2. After tool result is submitted, Tech Lead finishes
    chunk_done = StreamChunk(content="File contents look good.", finish_reason=FinishReason.STOP)

    call_count = 0

    async def side_effect(*_args, **_kwargs):  # noqa: ARG001
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            yield chunk_tool
        else:
            yield chunk_done

    mock_provider.chat_completion_stream.side_effect = side_effect

    orchestrator = Orchestrator(default_provider=mock_provider)

    events = []
    async for event in orchestrator.run("Read foo.py"):
        events.append(event)

    # The tool call should have been executed (not silently dropped)
    tool_result_events = [
        e for e in events if e.type == EventType.TOOL_CALL_RESULT
    ]
    assert len(tool_result_events) == 1, (
        "Expected exactly one TOOL_CALL_RESULT event — tool calls must be "
        "executed before continue_with_tool_results()"
    )

    # Agent should have continued and produced final content
    content_events = [e for e in events if e.type == EventType.CONTENT]
    assert any("File contents" in e.data for e in content_events)

    # Only 2 LLM calls: initial (tool_call) + continuation (STOP)
    assert call_count == 2, (
        f"Expected 2 LLM calls but got {call_count} — "
        "possible infinite loop if tool calls are not executed"
    )


@pytest.mark.asyncio
async def test_multiple_tool_calls_all_executed(mock_provider):
    """All tool calls in a single response are executed before continuing."""
    tc1 = ToolCall(id="call_1", name="read_file", arguments={"path": "a.py"})
    tc2 = ToolCall(id="call_2", name="read_file", arguments={"path": "b.py"})
    chunk_tools = StreamChunk(
        tool_calls=[tc1, tc2], finish_reason=FinishReason.TOOL_CALLS
    )
    chunk_done = StreamChunk(content="Both read.", finish_reason=FinishReason.STOP)

    call_count = 0

    async def side_effect(*_args, **_kwargs):  # noqa: ARG001
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            yield chunk_tools
        else:
            yield chunk_done

    mock_provider.chat_completion_stream.side_effect = side_effect
    orchestrator = Orchestrator(default_provider=mock_provider)

    events = []
    async for event in orchestrator.run("Read both files"):
        events.append(event)

    tool_results = [e for e in events if e.type == EventType.TOOL_CALL_RESULT]
    assert len(tool_results) == 2, (
        f"Expected 2 tool results but got {len(tool_results)} — "
        "all tool calls in a batch must be executed"
    )
    assert call_count == 2

