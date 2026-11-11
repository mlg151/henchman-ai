"""Chat publication uses held evidence policy without changing agent inputs."""

import asyncio
import json
import logging
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from henchman.chat.base import ChatMessage, ChatPlatform
from henchman.chat.manager import ChatManager
from henchman.config.schema import Settings
from henchman.core.events import AgentEvent, EventType
from henchman.providers.base import FinishReason, Message, ModelProvider, StreamChunk, ToolCall
from henchman.tools.base import ToolResult
from henchman.utils.evidence_redaction import REDACTED


def message(content="ordinary request"):
    return ChatMessage("message-id", "user", "person", content,
                       datetime.now(UTC), ChatPlatform.DISCORD)


def setup_chat(secret="chat-content-private-value", *, delivered=True):
    manager = ChatManager(Settings())
    bot = SimpleNamespace(send_message=AsyncMock(return_value=delivered),
                          send_typing=AsyncMock())
    actor = SimpleNamespace(provider=SimpleNamespace(api_key=secret), messages=[],
                            submit_tool_result=AsyncMock())
    manager._bots[ChatPlatform.DISCORD] = bot
    manager._user_agents["user"] = actor
    return manager, bot, actor


def sent(bot):
    return "\n".join(call.args[1] for call in bot.send_message.call_args_list)


async def test_received_log_projects_before_clip_and_preserves_raw_input(caplog):
    secret = "chat-received-private-value"
    manager, bot, actor = setup_chat(secret)
    incoming = message("x" * 90 + secret)

    async def run(user_input):
        actor.messages.append(user_input)
        yield AgentEvent(EventType.CONTENT, "safe reply")
        yield AgentEvent(EventType.FINISHED, {"finish_reason": "stop"})

    actor.run = run
    caplog.set_level(logging.INFO, logger="henchman.chat.manager")
    await manager._handle_message(incoming)
    assert "chat-recei" not in caplog.text
    assert REDACTED in caplog.text
    assert actor.messages == [incoming.content]
    assert manager._user_histories["user"][0]["content"] == incoming.content
    assert sent(bot) == "safe reply"


@pytest.mark.parametrize("escaped", [False, True])
async def test_split_credential_flush_and_final_are_projected_without_raw_history_mutation(escaped):
    secret = 'chat-content-"private\\value'
    wire = json.dumps(secret)[1:-1] if escaped else secret
    manager, bot, actor = setup_chat(secret)
    raw = "a" * 1795 + wire + " final answer"

    async def run(user_input):
        actor.messages.extend([user_input, raw])
        yield AgentEvent(EventType.CONTENT, "a" * 1795 + wire[:12])
        yield AgentEvent(EventType.CONTENT, wire[12:] + " final answer")
        yield AgentEvent(EventType.FINISHED, {"finish_reason": "stop"})

    actor.run = run
    await manager._handle_message(message())
    assert "chat-content" not in sent(bot)
    assert REDACTED in sent(bot) and "final answer" in sent(bot)
    assert actor.messages == ["ordinary request", raw]
    assert manager._user_histories["user"][-1]["content"] == sent(bot)


@pytest.mark.parametrize("finish", ["stop", "length", "error", "exhausted"])
async def test_prefix_finalization_distinguishes_success_from_interruption(finish):
    manager, bot, actor = setup_chat()
    prefix = "chat-content-priv"

    async def run(**_inputs):
        yield AgentEvent(EventType.CONTENT, "answer " + prefix)
        if finish == "error":
            yield AgentEvent(EventType.ERROR, "ordinary failure")
        elif finish != "exhausted":
            yield AgentEvent(EventType.FINISHED, {"finish_reason": finish})

    actor.run = run
    await manager._handle_message(message())
    if finish == "stop":
        assert prefix in sent(bot)
    else:
        assert prefix not in sent(bot)
        assert REDACTED in sent(bot)


async def test_split_header_and_actor_rotation_use_current_and_retained_policy():
    old, new = "previous-chat-key", "rotated-chat-key"
    manager, bot, actor = setup_chat(old)

    async def run(**_inputs):
        yield AgentEvent(EventType.CONTENT, "answer ")
        actor.provider.api_key = new
        yield AgentEvent(EventType.CONTENT, old + " " + new[:8])
        yield AgentEvent(EventType.CONTENT, new[8:] + "\nAuthoriz")
        yield AgentEvent(EventType.CONTENT, "ation: Bearer unknown-header-token\nend")
        yield AgentEvent(EventType.FINISHED, None)

    actor.run = run
    await manager._handle_message(message())
    output = sent(bot)
    assert old not in output and new not in output
    assert "unknown-header-token" not in output
    assert "end" in output and output.count(REDACTED) >= 3


async def test_finish_refreshes_actor_policy_for_previously_buffered_content():
    manager, bot, actor = setup_chat()
    new = "learned-at-finish-private"

    async def stream():
        yield AgentEvent(EventType.CONTENT, "answer " + new)
        actor.provider.api_key = new
        yield AgentEvent(EventType.FINISHED, None)

    _, pending, _ = await manager._process_stream(actor, bot, "user", stream(), [], "")
    assert pending == "answer " + REDACTED


async def test_failed_projected_delivery_is_not_recorded():
    manager, bot, actor = setup_chat(delivered=False)

    async def run(**_inputs):
        yield AgentEvent(EventType.CONTENT, actor.provider.api_key)
        yield AgentEvent(EventType.FINISHED, None)

    actor.run = run
    await manager._handle_message(message())
    assert sent(bot) == REDACTED
    assert manager._user_histories.get("user", []) == []


async def test_cancellation_keeps_primary_and_never_publishes_held_prefix():
    manager, bot, actor = setup_chat()
    primary = asyncio.CancelledError("original chat cancellation")

    async def run(**_inputs):
        yield AgentEvent(EventType.CONTENT, "a" * 1795 + "chat-content-priv")
        raise primary

    actor.run = run
    with pytest.raises(asyncio.CancelledError) as caught:
        await manager._handle_message(message())
    assert caught.value is primary
    assert "chat-content-priv" not in sent(bot)
    assert manager._user_histories.get("user", []) == []


async def test_tool_marked_value_projects_pending_content_without_changing_execution():
    secret = "marked-chat-tool-private"
    manager, bot, actor = setup_chat()
    args = {"api_key": secret}
    result = ToolResult(success=True, content="execution " + secret)
    actor.tool_registry = SimpleNamespace(execute=AsyncMock(return_value=result))
    submitted = []
    actor.submit_tool_result = lambda *values: submitted.append(values)

    async def run(**_inputs):
        yield AgentEvent(EventType.CONTENT, "using " + secret)
        yield AgentEvent(EventType.TOOL_CALL_REQUEST, ToolCall("call", "offline_tool", args))
        yield AgentEvent(EventType.FINISHED, {"finish_reason": "tool_calls"})

    async def continuation():
        yield AgentEvent(EventType.CONTENT, "done")
        yield AgentEvent(EventType.FINISHED, None)

    actor.run = run
    actor.continue_with_tool_results = continuation
    await manager._handle_message(message())
    assert secret not in sent(bot)
    actor.tool_registry.execute.assert_awaited_once_with("offline_tool", args)
    assert submitted == [("call", result)] and args == {"api_key": secret}


async def test_history_refreshes_rotated_policy_before_preview_clipping():
    manager, bot, actor = setup_chat()
    new = "history-rotated-private"
    raw = "x" * 90 + new
    manager._user_histories["user"] = [{"role": "user", "content": raw}]
    actor.provider.api_key = new
    await manager._handle_message(message("/history"))
    assert "history-ro" not in sent(bot)
    assert REDACTED in sent(bot)
    assert manager._user_histories["user"][0]["content"] == raw


async def test_actual_agent_retains_raw_provider_conversation_only_chat_output_is_projected():
    from henchman.core.agent import Agent

    secret = "actual-chat-provider-private"
    observed = []

    class Provider(ModelProvider):
        name = "offline"
        api_key = secret

        async def chat_completion_stream(self, messages, **_kwargs):
            observed.extend(messages)
            yield StreamChunk(content="answer " + secret[:10])
            yield StreamChunk(content=secret[10:])
            yield StreamChunk(finish_reason=FinishReason.STOP)

    manager, bot, _ = setup_chat(secret)
    actor = Agent(provider=Provider())
    manager._user_agents["user"] = actor
    incoming = message("please explain " + secret)
    await manager._handle_message(incoming)
    assert Message(role="user", content=incoming.content) in observed
    assert actor.messages[-1].content == "answer " + secret
    assert sent(bot) == "answer " + REDACTED
    assert manager._user_histories["user"] == [
        {"role": "user", "content": incoming.content},
        {"role": "assistant", "content": "answer " + REDACTED},
    ]
