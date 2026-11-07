"""Scripted HTTP streams for real SDK clients, including their retry-free copies."""

from __future__ import annotations

import json
from collections.abc import Callable
from importlib import import_module
from typing import Any

from henchman.providers.anthropic import AnthropicProvider

ScriptedCall = tuple[str, str, dict[str, Any]] | None
_ANSWER = "Fixed the addition bug; pytest now passes."


def _compatible_body(call: ScriptedCall, model: str) -> bytes:
    def chunk(delta: dict[str, Any], finish: str | None = None) -> dict[str, Any]:
        return {
            "id": "completion", "object": "chat.completion.chunk", "created": 1,
            "model": model,
            "choices": [{"index": 0, "delta": delta, "finish_reason": finish}],
        }

    if call is None:
        chunks = [chunk({"content": _ANSWER}, "stop")]
    else:
        arguments = json.dumps(call[2])
        chunks = [
            chunk({"tool_calls": [{
                "index": 0, "id": call[0], "type": "function",
                "function": {"name": call[1], "arguments": arguments[:8]},
            }]}),
            chunk({"tool_calls": [{"index": 0, "function": {"arguments": arguments[8:]}}]}),
            chunk({}, "tool_calls"),
        ]
    chunks.append({
        "id": "completion", "object": "chat.completion.chunk", "created": 1,
        "model": model, "choices": [],
        "usage": {"prompt_tokens": 10, "completion_tokens": 10, "total_tokens": 20},
    })
    return ("".join(f"data: {json.dumps(chunk)}\n\n" for chunk in chunks)
            + "data: [DONE]\n\n").encode()


def _native_body(call: ScriptedCall, model: str) -> bytes:
    block = (
        {"type": "tool_use", "id": call[0], "name": call[1], "input": {}}
        if call else {"type": "text", "text": ""}
    )
    delta = (
        {"type": "input_json_delta", "partial_json": json.dumps(call[2])}
        if call else {"type": "text_delta", "text": _ANSWER}
    )
    events: list[dict[str, Any]] = [{
        "type": "message_start", "message": {
            "id": "message-1", "type": "message", "role": "assistant", "model": model,
            "content": [], "stop_reason": None, "stop_sequence": None,
            "usage": {"input_tokens": 10, "output_tokens": 0},
        },
    }, {
        "type": "content_block_start", "index": 0, "content_block": block,
    }, {
        "type": "content_block_delta", "index": 0, "delta": delta,
    }, {
        "type": "content_block_stop", "index": 0,
    }, {
        "type": "message_delta",
        "delta": {"stop_reason": "tool_use" if call else "end_turn", "stop_sequence": None},
        "usage": {"output_tokens": 10},
    }, {"type": "message_stop"}]
    return "".join(
        f"event: {event['type']}\ndata: {json.dumps(event)}\n\n" for event in events
    ).encode()


async def bind_scripted_transport(
    provider: Any, next_call: Callable[..., ScriptedCall],
) -> None:
    """Replace only HTTP I/O; request formatting and SDK stream parsing stay real.

    The caller closes the provider client after its run. SDK ``with_options``
    copies retain this HTTP client and cannot bypass the fixture transport.
    """
    http_name = next(
        cls.__module__.partition(".")[0] for cls in type(provider._client._client).__mro__
        if cls.__module__.partition(".")[0] in {"httpx", "httpx2"}
    )
    http = import_module(http_name)
    native = isinstance(provider, AnthropicProvider)

    async def respond(request: Any) -> Any:
        assert request.url.host == "offline.invalid"
        payload = json.loads(request.content)
        call = next_call(**payload)
        encode = _native_body if native else _compatible_body
        return http.Response(
            200, content=encode(call, payload["model"]),
            headers={"content-type": "text/event-stream"},
        )

    client_class = type(provider._client)
    await provider._client.close()
    provider._client = client_class(
        api_key="offline-test", base_url="https://offline.invalid/v1",
        http_client=http.AsyncClient(transport=http.MockTransport(respond), trust_env=False),
    )
