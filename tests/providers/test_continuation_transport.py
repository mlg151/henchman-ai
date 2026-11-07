"""Real SDK parsing and wire capture for provider continuation, entirely offline."""

import json
from importlib import import_module

import pytest

from henchman.core.agent import Agent
from henchman.core.events import EventType
from henchman.providers.anthropic import AnthropicProvider
from henchman.providers.base import Message
from henchman.providers.continuation import ProviderContinuationError
from henchman.providers.deepseek import DeepSeekProvider
from henchman.providers.openai_compat import OpenAICompatibleProvider
from henchman.providers.openrouter import OpenRouterProvider


async def bind(provider, bodies):
    http_name = next(cls.__module__.partition(".")[0] for cls in type(provider._client._client).__mro__
                     if cls.__module__.partition(".")[0] in {"httpx", "httpx2"})
    http = import_module(http_name)
    requests = []
    async def respond(request):
        assert request.url.host == "offline.invalid"
        requests.append(json.loads(request.content))
        assert len(requests) <= len(bodies)
        return http.Response(200, content=bodies[len(requests) - 1], headers={"content-type": "text/event-stream"})
    old = provider._client
    provider._client = type(old)(api_key="offline-test", base_url="https://offline.invalid/v1",
                                http_client=http.AsyncClient(transport=http.MockTransport(respond), trust_env=False))
    await old.close()
    return requests


def native_body(blocks, *, finish="tool_use", incomplete_signature=False):
    events = [{"type": "message_start", "message": {"id": "msg", "type": "message", "role": "assistant",
        "model": "model-a", "content": [], "stop_reason": None, "stop_sequence": None,
        "usage": {"input_tokens": 10, "output_tokens": 0}}}]
    for index, block in enumerate(blocks):
        kind = block["type"]
        start = dict(block)
        if kind == "thinking":
            start.update(thinking="", signature="")
        elif kind == "text":
            start["text"] = ""
        elif kind == "tool_use":
            start["input"] = {}
        events.append({"type": "content_block_start", "index": index, "content_block": start})
        deltas = []
        if kind == "thinking":
            deltas.append({"type": "thinking_delta", "thinking": block["thinking"]})
            if not incomplete_signature:
                deltas.append({"type": "signature_delta", "signature": block["signature"]})
        elif kind == "text":
            deltas.append({"type": "text_delta", "text": block["text"]})
        elif kind == "tool_use":
            deltas.append({"type": "input_json_delta", "partial_json": json.dumps(block["input"])})
        events.extend({"type": "content_block_delta", "index": index, "delta": delta} for delta in deltas)
        events.append({"type": "content_block_stop", "index": index})
    events.extend([{"type": "message_delta", "delta": {"stop_reason": finish, "stop_sequence": None}, "usage": {"output_tokens": 5}},
                   {"type": "message_stop"}])
    return "".join(f"event: {item['type']}\ndata: {json.dumps(item)}\n\n" for item in events).encode()


def compatible_body(deltas, *, finish="tool_calls"):
    chunks = [{"id": "completion", "object": "chat.completion.chunk", "created": 1, "model": "model-a",
               "choices": [{"index": 0, "delta": delta, "finish_reason": None}]} for delta in deltas]
    chunks.append({"id": "completion", "object": "chat.completion.chunk", "created": 1, "model": "model-a",
                   "choices": [{"index": 0, "delta": {}, "finish_reason": finish}]})
    return ("".join(f"data: {json.dumps(item)}\n\n" for item in chunks) + "data: [DONE]\n\n").encode()


def tool_delta():
    return {"tool_calls": [{"index": 0, "id": "call", "type": "function", "function": {"name": "inspect", "arguments": "{}"}}]}


@pytest.mark.parametrize("thought", ["inspect state", ""])
async def test_native_signed_and_redacted_blocks_survive_tool_roundtrip(thought):
    blocks = [{"type": "thinking", "thinking": thought, "signature": "opaque-signature"},
              {"type": "text", "text": "Inspecting."},
              {"type": "redacted_thinking", "data": "encrypted-opaque"},
              {"type": "tool_use", "id": "call", "name": "inspect", "input": {}}]
    provider = AnthropicProvider(api_key="offline-test", model="model-a", max_retries=0, tokens_per_minute=1000000)
    requests = await bind(provider, [native_body(blocks), native_body([{"type": "text", "text": "Done"}], finish="end_turn")])
    try:
        agent = Agent(provider=provider)
        events = [event async for event in agent.run("Inspect")]
        assert any(event.type == EventType.TOOL_CALL_REQUEST for event in events)
        assert agent.messages[-1].continuation is not None
        assert "opaque-signature" not in repr(events) and "encrypted-opaque" not in repr(events)
        agent.submit_tool_result("call", "Observed")
        _ = [event async for event in agent.continue_with_tool_results()]
        assistant = next(message for message in requests[1]["messages"] if message["role"] == "assistant")
        assert assistant["content"] == blocks
    finally:
        await provider._client.close()


@pytest.mark.parametrize("name", ["openrouter", "deepseek"])
async def test_compatible_reasoning_profile_is_returned_to_same_provider(name):
    provider_type = OpenRouterProvider if name == "openrouter" else DeepSeekProvider
    provider = provider_type(api_key="offline-test", model="model-a")
    details = [{"type": "reasoning.text", "text": "fragment", "signature": None, "index": 0},
               {"type": "reasoning.encrypted", "data": "encrypted-opaque", "index": 1}]
    reasoning = ([{"reasoning_details": [detail]} for detail in details] if name == "openrouter"
                 else [{"reasoning_content": "part "}, {"reasoning_content": "two"}])
    requests = await bind(provider, [compatible_body([*reasoning, tool_delta()]), compatible_body([{"content": "Done"}], finish="stop")])
    try:
        agent = Agent(provider=provider)
        events = [event async for event in agent.run("Inspect")]
        assert agent.messages[-1].continuation is not None
        assert "encrypted-opaque" not in repr(events)
        agent.submit_tool_result("call", "Observed")
        _ = [event async for event in agent.continue_with_tool_results()]
        assistant = next(message for message in requests[1]["messages"] if message["role"] == "assistant")
        if name == "openrouter":
            assert assistant["reasoning_details"] == details
        else:
            assert assistant["reasoning_content"] == "part two"
    finally:
        await provider._client.close()


async def test_missing_native_signature_fails_before_any_tool_request():
    provider = AnthropicProvider(api_key="offline-test", model="model-a", max_retries=0)
    blocks = [{"type": "thinking", "thinking": "thought", "signature": "not-sent"},
              {"type": "tool_use", "id": "call", "name": "inspect", "input": {}}]
    await bind(provider, [native_body(blocks, incomplete_signature=True)])
    events = []
    try:
        with pytest.raises(ProviderContinuationError):
            async for event in Agent(provider=provider).run("Inspect"):
                events.append(event)
        assert not any(event.type == EventType.TOOL_CALL_REQUEST for event in events)
    finally:
        await provider._client.close()


async def test_unsupported_compatible_endpoint_cannot_silently_drop_opaque_details():
    provider = OpenAICompatibleProvider(api_key="offline-test", base_url="https://offline.invalid/v1", default_model="model-a")
    await bind(provider, [compatible_body([{"reasoning_details": [{"type": "reasoning.encrypted", "data": "opaque"}]}, tool_delta()])])
    try:
        with pytest.raises(ProviderContinuationError):
            _ = [chunk async for chunk in provider.chat_completion_stream([Message("user", "Inspect")])]
    finally:
        await provider._client.close()


async def test_incomplete_native_stream_blocks_later_dispatch_and_retains_visible_text():
    provider = AnthropicProvider(api_key="offline-test", model="model-a", max_retries=0)
    blocks = [{"type": "thinking", "thinking": "Observed thought", "signature": "never-sent"}]
    requests = await bind(provider, [native_body(blocks, finish="end_turn", incomplete_signature=True)])
    agent = Agent(provider)
    try:
        with pytest.raises(ProviderContinuationError):
            _ = [event async for event in agent.run("Inspect")]
        assert agent.messages[-1].reasoning_content == "Observed thought"
        assert agent.messages[-1].continuation["status"] == "unavailable"
        with pytest.raises(ProviderContinuationError, match="unavailable"):
            _ = [event async for event in agent.run("Continue")]
        assert len(requests) == 1
    finally:
        await provider._client.close()


@pytest.mark.parametrize("name", ["anthropic", "openrouter", "deepseek"])
async def test_durable_roundtrip_resumes_exact_payload_and_rejects_model_override_before_http(name, tmp_path):
    from dataclasses import asdict

    from henchman.cli.session_manager import _sync_messages_to_agent
    from henchman.core.session import Session, SessionMessage, session_from_json

    types = {"anthropic": AnthropicProvider, "openrouter": OpenRouterProvider, "deepseek": DeepSeekProvider}
    provider = types[name](api_key="offline-test", model="model-a")
    blocks = [{"type": "thinking", "thinking": "Inspect", "signature": "opaque-signature"},
              {"type": "tool_use", "id": "call", "name": "inspect", "input": {}}]
    deltas = [{"reasoning_details": [{"type": "reasoning.encrypted", "data": "opaque"}]}] if name == "openrouter" else [{"reasoning_content": "Inspect"}]
    bodies = [native_body(blocks), native_body([{"type": "text", "text": "Done"}], finish="end_turn")] if name == "anthropic" else [compatible_body([*deltas, tool_delta()]), compatible_body([{"content": "Done"}], finish="stop")]
    requests = await bind(provider, bodies)
    try:
        agent = Agent(provider)
        _ = [event async for event in agent.run("Inspect")]
        agent.submit_tool_result("call", "Observed")
        session = Session("s", "p", "now", "now", messages=[SessionMessage(**asdict(message)) for message in agent.messages])
        path = tmp_path / "resume.json"
        path.write_text(session.to_json())
        restored = Agent(provider)
        _sync_messages_to_agent(restored, session_from_json(path.read_text()))
        with pytest.raises(ProviderContinuationError, match="incompatible"):
            _ = [chunk async for chunk in provider.chat_completion_stream(restored.messages, extra_body={"model": "changed"})]
        assert len(requests) == 1
        _ = [chunk async for chunk in provider.chat_completion_stream(restored.messages)]
        assert len(requests) == 2
        assert restored.messages[-2].continuation == agent.messages[-2].continuation
    finally:
        await provider._client.close()


async def test_native_stream_without_message_stop_cannot_execute_tool():
    provider = AnthropicProvider(api_key="offline-test", model="model-a", max_retries=0)
    blocks = [{"type": "thinking", "thinking": "Inspect", "signature": "signature"},
              {"type": "tool_use", "id": "call", "name": "inspect", "input": {}}]
    incomplete = native_body(blocks).split(b"event: message_stop")[0]
    await bind(provider, [incomplete])
    events = []
    try:
        with pytest.raises(ProviderContinuationError, match="incomplete"):
            async for event in Agent(provider).run("Inspect"):
                events.append(event)
        assert not any(event.type == EventType.TOOL_CALL_REQUEST for event in events)
    finally:
        await provider._client.close()


async def test_compatible_reasoning_after_finish_cannot_execute_tool():
    provider = OpenRouterProvider(api_key="offline-test", model="model-a")
    first = compatible_body([{"reasoning_details": [{"type": "reasoning.encrypted", "data": "opaque"}]}, tool_delta()])
    trailing = compatible_body([{"reasoning_details": [{"type": "reasoning.encrypted", "data": "late"}]}])
    await bind(provider, [first.replace(b"data: [DONE]\n\n", b"") + trailing])
    events = []
    try:
        with pytest.raises(ProviderContinuationError):
            async for event in Agent(provider).run("Inspect"):
                events.append(event)
        assert not any(event.type == EventType.TOOL_CALL_REQUEST for event in events)
    finally:
        await provider._client.close()


async def test_native_request_thinking_configuration_cannot_change_inside_tool_exchange():
    provider = AnthropicProvider(api_key="offline-test", model="model-a", max_retries=0)
    blocks = [{"type": "thinking", "thinking": "Inspect", "signature": "signature"},
              {"type": "tool_use", "id": "call", "name": "inspect", "input": {}}]
    requests = await bind(provider, [native_body(blocks), native_body([{"type": "text", "text": "Done"}], finish="end_turn")])
    thinking = {"type": "enabled", "budget_tokens": 1024}
    try:
        chunks = [chunk async for chunk in provider.chat_completion_stream([Message("user", "Inspect")], thinking=thinking)]
        final = next(chunk for chunk in chunks if chunk.continuation is not None and chunk.continuation["status"] == "complete")
        messages = [Message("user", "Inspect"), Message("assistant", "", tool_calls=final.tool_calls,
                    reasoning_content="Inspect", continuation=final.continuation), Message("tool", "Observed", tool_call_id="call")]
        with pytest.raises(ProviderContinuationError, match="incompatible"):
            _ = [chunk async for chunk in provider.chat_completion_stream(messages)]
        assert len(requests) == 1
        _ = [chunk async for chunk in provider.chat_completion_stream(messages, thinking=thinking)]
        assert len(requests) == 2
    finally:
        await provider._client.close()


async def test_visible_reasoning_is_not_implicitly_replayed_as_opaque_state():
    provider = OpenAICompatibleProvider(api_key="offline-test", base_url="https://offline.invalid/v1", default_model="model-a")
    requests = await bind(provider, [compatible_body([{"content": "Done"}], finish="stop")])
    try:
        _ = [chunk async for chunk in provider.chat_completion_stream([
            Message("user", "Inspect"), Message("assistant", "Done", reasoning_content="visible only"), Message("user", "Continue")])]
        assert "reasoning_content" not in requests[0]["messages"][1]
    finally:
        await provider._client.close()


async def test_opaque_finish_does_not_overwrite_trailing_usage_with_an_earlier_snapshot():
    provider = OpenRouterProvider(api_key="offline-test", model="model-a")
    first = compatible_body([{"reasoning_details": [{"type": "reasoning.encrypted", "data": "opaque"}]}, {"content": "Done"}], finish="stop")
    trailer = {"id": "completion", "object": "chat.completion.chunk", "created": 1, "model": "model-a",
               "choices": [], "usage": {"prompt_tokens": 55, "completion_tokens": 7, "total_tokens": 62}}
    body = first.replace(b"data: [DONE]\n\n", f"data: {json.dumps(trailer)}\n\ndata: [DONE]\n\n".encode())
    await bind(provider, [body])
    try:
        events = [event async for event in Agent(provider).run("Answer")]
        finish = next(event for event in events if event.type == EventType.FINISHED)
        assert finish.data["usage"] == {"prompt_tokens": 55, "completion_tokens": 7, "total_tokens": 62}
    finally:
        await provider._client.close()


@pytest.mark.parametrize("provider_type", [AnthropicProvider, DeepSeekProvider])
async def test_legacy_reasoning_tool_exchange_cannot_invent_missing_continuation(provider_type):
    from henchman.providers.base import ToolCall

    provider = provider_type(api_key="offline-test", model="model-a")
    requests = await bind(provider, [])
    messages = [Message("user", "Inspect"), Message("assistant", "", tool_calls=[ToolCall("call", "inspect", {})],
                reasoning_content="Visible legacy thought"), Message("tool", "Observed", tool_call_id="call")]
    try:
        with pytest.raises(ProviderContinuationError, match="unqualified_legacy"):
            _ = [chunk async for chunk in provider.chat_completion_stream(messages)]
        assert requests == []
        assert messages[1].reasoning_content == "Visible legacy thought"
    finally:
        await provider._client.close()


async def test_deepseek_tool_stream_with_only_unqualified_reasoning_alias_stops_before_tools():
    provider = DeepSeekProvider(api_key="offline-test", model="model-a")
    requests = await bind(provider, [compatible_body([{"reasoning": "Visible thought"}, tool_delta()])])
    agent = Agent(provider)
    events = []
    try:
        with pytest.raises(ProviderContinuationError):
            async for event in agent.run("Inspect"):
                events.append(event)
        assert not any(event.type == EventType.TOOL_CALL_REQUEST for event in events)
        assert agent.messages[-1].continuation["status"] == "unavailable"
        assert len(requests) == 1
    finally:
        await provider._client.close()


async def test_request_default_model_is_the_continuation_identity_through_agent_roundtrip():
    provider = OpenRouterProvider(api_key="offline-test", model="display-model")
    provider.request_defaults = {"extra_body": {"model": "wire-model"}}
    requests = await bind(provider, [compatible_body([{"reasoning_details": [{"type": "reasoning.encrypted", "data": "opaque"}]}, tool_delta()]),
                                     compatible_body([{"content": "Done"}], finish="stop")])
    agent = Agent(provider)
    try:
        _ = [event async for event in agent.run("Inspect")]
        assert agent.messages[-1].continuation["model"] == "wire-model"
        agent.submit_tool_result("call", "Observed")
        _ = [event async for event in agent.continue_with_tool_results()]
        assert [request["model"] for request in requests] == ["wire-model", "wire-model"]
    finally:
        await provider._client.close()


@pytest.mark.parametrize("name", ["anthropic", "openrouter", "deepseek", "openai_compat"])
async def test_first_opaque_data_after_tool_finish_cannot_escape_as_an_executable_request(name):
    types = {"anthropic": AnthropicProvider, "openrouter": OpenRouterProvider, "deepseek": DeepSeekProvider,
             "openai_compat": OpenAICompatibleProvider}
    provider = (types[name](api_key="offline-test", model="model-a") if name != "openai_compat" else
                OpenAICompatibleProvider(api_key="offline-test", base_url="https://offline.invalid/v1", default_model="model-a"))
    if name == "anthropic":
        normal = native_body([{"type": "tool_use", "id": "call", "name": "inspect", "input": {}}])
        late = native_body([{"type": "thinking", "thinking": "late", "signature": "opaque"}])
        blocks = b"event: content_block_start" + late.split(b"event: content_block_start", 1)[1].split(b"event: message_delta", 1)[0]
        blocks = blocks.replace(b'"index": 0', b'"index": 1')
        body = normal.replace(b"event: message_stop", blocks + b"event: message_stop")
    else:
        normal = compatible_body([tool_delta()]).replace(b"data: [DONE]\n\n", b"")
        extra = {"reasoning_content": "late"} if name == "deepseek" else {"reasoning_details": [{"type": "reasoning.encrypted", "data": "late"}]}
        body = normal + compatible_body([extra])
    await bind(provider, [body])
    events = []
    try:
        with pytest.raises(ProviderContinuationError):
            async for event in Agent(provider).run("Inspect"):
                events.append(event)
        assert not any(event.type == EventType.TOOL_CALL_REQUEST for event in events)
    finally:
        await provider._client.close()


@pytest.mark.parametrize("name", ["openrouter", "deepseek"])
async def test_opaque_accumulation_stops_before_copying_or_joining_beyond_limit(name):
    provider = (OpenRouterProvider if name == "openrouter" else DeepSeekProvider)(api_key="offline-test", model="model-a")
    fragment = "x" * (1024 * 1024)
    delta = ({"reasoning_details": [{"type": "reasoning.encrypted", "data": fragment}]} if name == "openrouter"
             else {"reasoning_content": fragment})
    await bind(provider, [compatible_body([delta] * 5 + [tool_delta()])])
    yielded = []
    try:
        with pytest.raises(ProviderContinuationError, match="too_large"):
            async for chunk in provider.chat_completion_stream([Message("user", "Inspect")]):
                yielded.append(chunk)
        # One unavailable marker plus at most three accepted one-MiB fragments.
        assert len(yielded) <= 4
        assert not any(chunk.tool_calls for chunk in yielded)
    finally:
        await provider._client.close()


async def test_nonempty_native_message_start_cannot_hide_required_blocks():
    provider = AnthropicProvider(api_key="offline-test", model="model-a", max_retries=0)
    body = native_body([{"type": "tool_use", "id": "call", "name": "inspect", "input": {}}])
    body = body.replace(b'"content": []', b'"content": [{"type": "thinking", "thinking": "hidden", "signature": "opaque"}]', 1)
    body = body.replace(b'"index": 0', b'"index": 1')
    await bind(provider, [body])
    events = []
    try:
        with pytest.raises(ProviderContinuationError):
            async for event in Agent(provider).run("Inspect"):
                events.append(event)
        assert not any(event.type == EventType.TOOL_CALL_REQUEST for event in events)
    finally:
        await provider._client.close()
