"""Bounded #20 evidence checks; only configured canaries, no network."""

import asyncio
import logging
from types import SimpleNamespace

import pytest

from henchman.config.schema import Settings
from henchman.core.agent import Agent
from henchman.core.events import AgentEvent, EventType
from henchman.providers.base import FinishReason, Message, ModelProvider, StreamChunk
from henchman.utils.compaction import _generate_summary_with_provider


class Provider(ModelProvider):
    name = "offline"

    def __init__(self, secret):
        self.api_key = secret

    async def chat_completion_stream(self, *args, **kwargs):
        yield StreamChunk(content="safe", finish_reason=FinishReason.STOP)


async def test_known_provider_key_not_in_direct_agent_debug_evidence(caplog, monkeypatch):
    secret = "audit-configured-provider-private"
    agent = Agent(provider=Provider(secret))

    async def stream():
        yield AgentEvent(EventType.FINISHED, {"status": "responded"})

    monkeypatch.setattr(agent, "_stream_with_stall_loop", stream)
    caplog.set_level(logging.DEBUG, logger="henchman.core.agent")
    async for _ in agent.run("echo " + secret):
        pass
    assert secret not in caplog.text


async def test_summary_failure_logs_do_not_expose_configured_provider_key(caplog):
    secret = "audit-configured-summary-private"

    class FailedProvider(Provider):
        async def chat_completion_stream(self, *args, **kwargs):
            raise OSError("summary transport failed: " + self.api_key)
            yield

    provider = FailedProvider(secret)
    result = await _generate_summary_with_provider(
        provider, [Message(role="user", content="safe")], lambda _: "safe"
    )
    assert result is None
    assert secret not in caplog.text
    assert all(record.exc_info is None for record in caplog.records)


async def test_chat_error_output_uses_configured_policy_without_actual_service(caplog):
    from henchman.chat.manager import ChatManager

    secret = "audit-configured-chat-private"
    manager = ChatManager(Settings(providers={"deepseek": {"api_key": secret}}))
    outputs = []

    async def send(_user, text):
        outputs.append(text)
        return True

    async def stream():
        yield AgentEvent(EventType.ERROR, "provider failed " + secret)

    await manager._process_stream(
        SimpleNamespace(), SimpleNamespace(send_message=send), "owned-user", stream(), [], ""
    )
    assert secret not in "\n".join(outputs)
    assert secret not in caplog.text


async def test_compatible_cleanup_cancel_does_not_log_known_provider_key(caplog, monkeypatch):
    from henchman.providers.openai_compat import OpenAICompatibleProvider

    secret = "audit-configured-compatible-cleanup-private"
    provider = OpenAICompatibleProvider(secret, "http://127.0.0.1:1/v1", "offline")
    primary = asyncio.CancelledError("original caller cancellation")

    class Response:
        def __aiter__(self):
            return self

        async def __anext__(self):
            raise primary

        async def close(self):
            raise OSError("response cleanup " + secret)

    async def request(*_args, **_kwargs):
        return Response()

    monkeypatch.setattr(provider, "_make_api_request", request)
    try:
        with pytest.raises(asyncio.CancelledError) as info:
            async for _ in provider.chat_completion_stream([Message(role="user", content="safe")]):
                pass
        assert info.value is primary
        assert secret not in caplog.text
    finally:
        await provider._client.close()


async def test_anthropic_cleanup_cancel_does_not_log_known_credential(caplog, monkeypatch):
    from henchman.providers.anthropic import _stream_context

    secret = "audit-configured-anthropic-cleanup-private"
    monkeypatch.setenv("ANTHROPIC_API_KEY", secret)
    primary = asyncio.CancelledError("original caller cancellation")

    class Manager:
        async def __aenter__(self):
            return object()

        async def __aexit__(self, *args):
            raise OSError("sdk cleanup " + secret)

    with pytest.raises(asyncio.CancelledError) as info:
        async with _stream_context(Manager()):
            raise primary
    assert info.value is primary
    assert secret not in caplog.text


async def test_agent_debug_redacts_full_input_before_cut_and_preserves_execution(
    caplog, monkeypatch
):
    old, new = "retained-agent-private", "rotated-agent-private-value"
    provider = Provider(old)
    agent = Agent(provider=provider)

    async def stream():
        yield AgentEvent(EventType.FINISHED, {"status": "responded"})

    monkeypatch.setattr(agent, "_stream_with_stall_loop", stream)
    caplog.set_level(logging.DEBUG, logger="henchman.core.agent")
    async for _ in agent.run("first safe task"):
        pass
    provider.api_key = new
    value = "x" * 90 + new + " then " + old
    async for _ in agent.run(value):
        pass
    assert "rotated-ag" not in caplog.text and old not in caplog.text
    assert agent.messages[-1].content == value


async def test_summary_cancel_cleanup_retains_old_current_keys_and_primary(caplog):
    old, new = "retained-summary-private", "rotated-summary-private"
    provider = Provider(old)
    primary = asyncio.CancelledError("keep original summary cancellation")
    failure = OSError("cleanup " + old + " " + new)

    class Stream:
        def __aiter__(self):
            return self

        async def __anext__(self):
            provider.api_key = new
            raise primary

        async def aclose(self):
            raise failure

    provider.chat_completion_stream = lambda **_kwargs: Stream()
    with pytest.raises(asyncio.CancelledError) as caught:
        await _generate_summary_with_provider(provider, [], lambda _: "unchanged prompt")
    assert caught.value is primary
    assert old not in caplog.text and new not in caplog.text
    assert all(record.exc_info is None for record in caplog.records)
    assert str(failure) == "cleanup " + old + " " + new


async def test_outer_summary_failure_refreshes_provider_policy(caplog, monkeypatch):
    from henchman.utils import compaction

    old, new = "outer-summary-old-private", "outer-summary-new-private"
    provider = Provider(old)
    failure = OSError(old + " " + new)

    async def fail(_self, _messages):
        provider.api_key = new
        raise failure

    monkeypatch.setattr(compaction.MessageSummarizer, "summarize", fail)
    result = compaction.CompactionResult(messages=[])
    assert (
        await compaction._attempt_summarization(result, [Message("user", "raw input")], provider)
        is result
    )
    assert old not in caplog.text and new not in caplog.text
    assert all(record.exc_info is None for record in caplog.records)


async def test_chat_tool_error_projects_current_and_prior_actor_credentials(caplog):
    from henchman.chat.manager import ChatManager
    from henchman.providers.base import ToolCall

    old, new = "chat-actor-old-private", "chat-actor-new-private"
    manager = ChatManager(Settings())
    provider = Provider(old)
    failure = OSError("tool failed " + old + " " + new)
    submitted, outputs = [], []
    original_args = {"content": old, "api_key": "marked-tool-private"}

    async def execute(_name, args):
        assert args is original_args
        provider.api_key = new
        raise failure

    agent = SimpleNamespace(
        provider=provider,
        tool_registry=SimpleNamespace(execute=execute),
        submit_tool_result=lambda identity, result: submitted.append((identity, result)),
    )

    async def send(_user, text):
        outputs.append(text)

    async def stream():
        yield AgentEvent(
            EventType.TOOL_CALL_REQUEST, ToolCall("unchanged-call", "fixture", original_args)
        )

    await manager._process_stream(
        agent, SimpleNamespace(send_message=send), "unchanged-user", stream(), [], ""
    )
    evidence = caplog.text + "\n".join(outputs)
    assert old not in evidence and new not in evidence
    assert all(record.exc_info is None for record in caplog.records)
    assert submitted == [("unchanged-call", "Error: " + str(failure))]
    assert original_args["content"] == old


@pytest.mark.parametrize("primary_kind", [asyncio.CancelledError, RuntimeError])
async def test_anthropic_context_preserves_primary_and_retained_actor_policy(caplog, primary_kind):
    from henchman.providers.anthropic import _stream_context

    old, new = "anthropic-old-private", "anthropic-new-private"
    provider = Provider(old)
    primary = primary_kind("original primary")
    failure = OSError("SDK cleanup " + old + " " + new)
    failure.add_note("Authorization: Bearer header-marked-private")

    class Manager:
        async def __aenter__(self):
            provider.api_key = new
            return object()

        async def __aexit__(self, *_args):
            raise failure

    with pytest.raises(primary_kind) as caught:
        async with _stream_context(Manager(), provider=provider):
            raise primary
    assert caught.value is primary
    assert old not in caplog.text and new not in caplog.text
    assert "header-marked-private" not in caplog.text
    assert all(record.exc_info is None for record in caplog.records)
    assert str(failure) == "SDK cleanup " + old + " " + new


async def test_chat_outer_failure_uses_actual_actor_without_changing_prompt(caplog, monkeypatch):
    from datetime import UTC, datetime

    from henchman.chat.base import ChatMessage, ChatPlatform
    from henchman.chat.manager import ChatManager

    old, new = "outer-chat-old-private", "outer-chat-new-private"
    manager = ChatManager(Settings())
    provider = Provider(old)
    failure = RuntimeError(old + " " + new)
    inputs, outputs = [], []

    async def run(user_input):
        inputs.append(user_input)
        provider.api_key = new
        raise failure
        yield

    agent = SimpleNamespace(provider=provider, run=run)

    async def get_agent(_user):
        return agent

    async def send(_user, text):
        outputs.append(text)
        return True

    async def typing(_user):
        return None

    monkeypatch.setattr(manager, "_get_or_create_agent", get_agent)
    manager._bots[ChatPlatform.DISCORD] = SimpleNamespace(send_message=send, send_typing=typing)
    message = ChatMessage(
        "message", "user", "username", "raw unchanged task", datetime.now(UTC), ChatPlatform.DISCORD
    )
    await manager._handle_message(message)
    assert inputs == [message.content]
    assert old not in caplog.text and new not in caplog.text
    assert all(record.exc_info is None for record in caplog.records)
    assert any("error occurred" in output for output in outputs)
    assert str(failure) == old + " " + new
