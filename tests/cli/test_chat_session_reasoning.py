"""Resuming a saved chat preserves private provider continuation text."""

from collections.abc import AsyncGenerator
from io import StringIO
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from openai.types.chat import ChatCompletionChunk
from rich.console import Console

from henchman.cli.commands import CommandContext
from henchman.cli.commands.chat import ChatCommand
from henchman.core.agent import Agent
from henchman.core.events import EventType
from henchman.core.session import SessionManager, SessionMessage
from henchman.providers.base import Message, ToolCall
from henchman.providers.openai_compat import OpenAICompatibleProvider
from tests.providers.stream_helpers import SDKResponse


@pytest.mark.asyncio
@pytest.mark.parametrize("lookup", ["tag", "id"])
async def test_resume_replays_reasoning_to_next_request_without_displaying_it(
    tmp_path: Path,
    lookup: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    hidden = "PRIVATE saved continuation reasoning"
    manager = SessionManager(data_dir=tmp_path / ".henchman" / "sessions")
    session = manager.create_session("project")
    session.tag = "saved-work"
    session.messages = [
        SessionMessage(role="user", content="Inspect the existing helper"),
        SessionMessage(
            role="assistant",
            content="Inspecting",
            reasoning_content=hidden,
            tool_calls=[{"id": "read-1", "name": "read_file", "arguments": {"path": "helper.py"}}],
        ),
        SessionMessage(role="tool", content="Existing helper found", tool_call_id="read-1"),
    ]
    manager.save(session)
    provider = OpenAICompatibleProvider("test", "https://test.invalid/v1", "test-model")

    async def stream() -> AsyncGenerator[ChatCompletionChunk]:
        yield ChatCompletionChunk.model_validate(
            {
                "id": "resumed-completion",
                "object": "chat.completion.chunk",
                "created": 1,
                "model": "test-model",
                "choices": [
                    {
                        "index": 0,
                        "delta": {"content": "The helper is available."},
                        "finish_reason": "stop",
                    }
                ],
            },
        )

    request = AsyncMock(side_effect=lambda **_kwargs: SDKResponse(stream()))
    monkeypatch.setattr(provider._client.chat.completions, "create", request)
    agent = Agent(provider, system_prompt="Current instructions")
    agent.messages.append(Message(role="user", content="Discard stale history"))
    output = StringIO()
    identifier = session.tag if lookup == "tag" else session.id
    ctx = CommandContext(
        console=Console(file=output),
        args=["resume", identifier],
        agent=agent,
        session_manager=manager,
        project_hash="project",
    )
    try:
        await ChatCommand().execute(ctx)
        assert manager.current is not session  # Restore the persisted copy, not a live object.
        assert manager.current is not None and manager.current.id == session.id
        events = [event async for event in agent.continue_with_tool_results()]
        assert not any(event.type == EventType.ERROR for event in events)
        request.assert_awaited_once()
        sent = request.call_args.kwargs["messages"]
        assert sent[2]["reasoning_content"] == hidden
        assert agent.messages[:4] == [
            Message(role="system", content="Current instructions"),
            Message(role="user", content="Inspect the existing helper"),
            Message(
                role="assistant",
                content="Inspecting",
                reasoning_content=hidden,
                tool_calls=[ToolCall("read-1", "read_file", {"path": "helper.py"})],
            ),
            Message(role="tool", content="Existing helper found", tool_call_id="read-1"),
        ]
        assert [message["role"] for message in sent] == ["system", "user", "assistant", "tool"]
        assert sent[2]["content"] == "Inspecting"
        assert sent[2]["tool_calls"][0]["id"] == sent[3]["tool_call_id"] == "read-1"
        assert "Resumed session" in output.getvalue()
        assert hidden not in output.getvalue()
        assert all(hidden not in str(event.data) for event in events)
        assert "".join(event.data for event in events if event.type == EventType.CONTENT) == (
            "The helper is available."
        )
    finally:
        await provider._client.close()
