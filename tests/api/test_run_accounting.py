"""Standalone API runs use real provider accounting without network access."""

from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager
from typing import Any

import httpx
import pytest
from openai import AsyncOpenAI

from henchman.config.schema import Settings
from henchman.providers.openai_compat import OpenAICompatibleProvider


class Transport:
    def __init__(self) -> None:
        self.requests: list[dict[str, Any]] = []
        self.tools = False
        self.wait = False
        self.usage = True
        self.started = asyncio.Event()
        self.release = asyncio.Event()

    async def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(json.loads(request.content))
        self.started.set()
        if self.wait:
            await self.release.wait()
        delta: dict[str, Any] = {"content": "Done"}
        reason = "stop"
        if self.tools:
            reason = "tool_calls"
            delta = {
                "tool_calls": [
                    {
                        "index": 0,
                        "id": "call-1",
                        "type": "function",
                        "function": {
                            "name": "read_file",
                            "arguments": '{"path":"one.txt"}',
                        },
                    }
                ]
            }
        base = {
            "id": "completion-1",
            "object": "chat.completion.chunk",
            "created": 1,
            "model": "test-model",
        }
        chunks = [
            {**base, "choices": [{"index": 0, "delta": delta, "finish_reason": reason}]},
            {
                **base,
                "choices": [],
                "usage": {"prompt_tokens": 10, "completion_tokens": 2, "total_tokens": 12},
            },
        ]
        if not self.usage:
            chunks = chunks[:1]
        body = "".join(f"data: {json.dumps(chunk)}\n\n" for chunk in chunks) + "data: [DONE]\n\n"
        return httpx.Response(200, content=body, headers={"content-type": "text/event-stream"})


@pytest.fixture
def api(monkeypatch):
    @asynccontextmanager
    async def mounted(settings: Settings | None = None):
        from henchman.api import auth, server
        from henchman.api.endpoints import chat, health
        from henchman.api.state import State

        settings = settings or Settings()
        runtime = State()
        provider = OpenAICompatibleProvider("test", "https://test.invalid", "test-model")
        await provider._client.close()
        transport = Transport()
        provider._client = AsyncOpenAI(
            api_key="test",
            http_client=httpx.AsyncClient(
                transport=httpx.MockTransport(transport),
            ),
        )
        for module in (auth, server, chat, health):
            monkeypatch.setattr(module, "state", runtime)
        monkeypatch.setattr(server, "load_settings", lambda: settings)
        monkeypatch.setattr(server, "create_configured_provider", lambda *_a, **_k: provider)
        try:
            async with (
                server.lifespan(server.app),
                httpx.AsyncClient(
                    transport=httpx.ASGITransport(app=server.app),
                    base_url="http://test",
                ) as client,
            ):
                yield client, transport, runtime
        finally:
            await provider._client.close()

    return mounted


def user(text: str = "Hello") -> dict[str, Any]:
    return {"messages": [{"role": "user", "content": text}]}


def continuation(run_id: str | None) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "messages": [{"role": "tool", "content": "file content", "tool_call_id": "call-1"}]
    }
    if run_id is not None:
        payload["run_id"] = run_id
    return payload


@pytest.mark.parametrize("endpoint", ["/v1/chat/completions", "/v1/chat/completions/stream"])
async def test_zero_request_cap_prevents_http(api, endpoint) -> None:
    settings = Settings.model_validate({"usage": {"limits": {"max_requests": 0}}})
    async with api(settings) as (client, transport, _):
        response = await client.post(endpoint, json=user())
        assert not transport.requests
        assert "request_limit" in response.text


async def test_api_factory_preserves_read_confirmation_requirement(api, tmp_path):
    from henchman.tools.builtins.file_read import ReadFileTool

    settings = Settings.model_validate({"tools": {"auto_approve_read": False}})
    async with api(settings) as (client, _, runtime):
        response = await client.post("/v1/chat/completions", json=user())
        run = runtime.chat_runs.find("unauthenticated-local", response.json()["run_id"])
        run.agent.tool_registry.register(ReadFileTool())
        run.agent.tool_registry.add_auto_approve_policy("read_file")
        target = tmp_path / "data.txt"
        target.write_text("unapproved read canary")
        result = await run.agent.tool_registry.execute("read_file", {"path": str(target)})
        assert not result.success
        assert "unapproved read canary" not in result.content


async def test_unsupported_api_sandbox_prevents_runtime_readiness(api):
    settings = Settings.model_validate({"tools": {"sandbox": "docker"}})
    async with api(settings) as (client, transport, runtime):
        response = await client.post("/v1/chat/completions", json=user())
        assert response.status_code == 503
        assert runtime.chat_runs is None
        assert not transport.requests
        assert (await client.get("/v1/ready")).status_code == 503


@pytest.mark.parametrize("endpoint", ["/v1/chat/completions", "/v1/chat/completions/stream"])
async def test_durable_without_session_binding_fails_before_dispatch(api, endpoint) -> None:
    settings = Settings.model_validate({"usage": {"persistence": "durable"}})
    async with api(settings) as (client, transport, _):
        response = await client.post(endpoint, json=user())
        assert response.status_code == 503
        assert "durable_accounting_requires_api_session" in response.text
        assert not transport.requests


async def test_tool_followup_reuses_budget_and_original_tool_calls(api) -> None:
    settings = Settings.model_validate({"usage": {"limits": {"max_requests": 1}}})
    async with api(settings) as (client, transport, _):
        transport.tools = True
        first = await client.post("/v1/chat/completions", json=user())
        assert first.status_code == 200, first.text
        body = first.json()
        assert body["message"]["tool_calls"][0]["id"] == "call-1"
        assert body["budget"]["consumed_requests"] == 1
        second = await client.post("/v1/chat/completions", json=continuation(body["run_id"]))
        assert second.status_code == 429
        assert second.json()["details"]["budget"]["run_id"] == body["run_id"]
        assert len(transport.requests) == 1


async def test_missing_unknown_or_foreign_run_cannot_reset_budget(api) -> None:
    settings = Settings.model_validate(
        {"api": {"require_auth": True, "api_keys": ["first", "second"]}}
    )
    async with api(settings) as (client, transport, _):
        transport.tools = True
        first = await client.post(
            "/v1/chat/completions", json=user(), headers={"X-API-Key": "first"}
        )
        run_id = first.json()["run_id"]
        for payload, key in (
            (continuation(None), "first"),
            (continuation("missing"), "first"),
            (continuation(run_id), "second"),
        ):
            response = await client.post(
                "/v1/chat/completions", json=payload, headers={"X-API-Key": key}
            )
            assert response.status_code in (404, 409, 422)
        for route in ("/v1/chat/history", "/v1/usage"):
            response = await client.get(
                route, params={"run_id": run_id}, headers={"X-API-Key": "second"}
            )
            assert response.status_code == 404
        assert len(transport.requests) == 1


async def test_concurrent_roots_have_distinct_agents_and_prompts(api) -> None:
    async with api() as (client, transport, _):
        transport.wait = True
        first = asyncio.create_task(
            client.post("/v1/chat/completions", json={**user("first"), "system_prompt": "FIRST"})
        )
        await transport.started.wait()
        second = asyncio.create_task(client.post("/v1/chat/completions", json=user("second")))
        for _ in range(100):
            if len(transport.requests) == 2:
                break
            await asyncio.sleep(0)
        transport.release.set()
        responses = await asyncio.gather(first, second)
        assert all(response.status_code == 200 for response in responses)
        assert responses[0].json()["run_id"] != responses[1].json()["run_id"]
        assert [message["content"] for message in transport.requests[0]["messages"]] == [
            "FIRST",
            "first",
        ]
        assert [message["content"] for message in transport.requests[1]["messages"]] == ["second"]


async def test_provider_error_event_is_not_successful_completion(api, monkeypatch) -> None:
    from henchman.core import Agent, AgentEvent, EventType

    async def fail(_self, _user_input):
        yield AgentEvent(EventType.ERROR, "provider failed")
        yield AgentEvent(EventType.FINISHED, {"finish_reason": "error"})

    monkeypatch.setattr(Agent, "run", fail)
    async with api() as (client, transport, runtime):
        response = await client.post("/v1/chat/completions", json=user())
        assert response.status_code == 500
        assert "provider failed" in response.text
        assert not transport.requests
        assert runtime.chat_runs.find("unauthenticated-local").interrupted


@pytest.mark.parametrize(
    "field,value",
    [
        ("max_tokens", 2),
        ("temperature", 0.0),
        ("max_tokens", None),
        ("model", "other"),
        ("tools", []),
    ],
)
async def test_unsupported_request_options_are_explicit(api, field, value) -> None:
    async with api() as (client, transport, _):
        response = await client.post("/v1/chat/completions", json={**user(), field: value})
        assert response.status_code == 422
        assert field in response.text
        assert not transport.requests


async def test_usage_is_owned_aggregate_with_unknown_cost_not_synthetic(api) -> None:
    async with api() as (client, transport, _):
        response = await client.post("/v1/chat/completions", json=user())
        report = (await client.get("/v1/usage")).json()
        assert (
            report["budget"] == response.json()["budget"]
            or report["budget"]["run_id"] == response.json()["run_id"]
        )
        assert report["accounting_lifetime"] == "process"
        assert report["total_cost"] is None
        assert report["budget"]["unknown_cost_requests"] == 1
        assert report["daily_usage"] == {}
        assert len(transport.requests) == 1


async def test_usage_rejects_invalid_auth(api) -> None:
    settings = Settings.model_validate({"api": {"require_auth": True, "api_keys": ["first"]}})
    async with api(settings) as (client, _, _):
        assert (await client.get("/v1/usage", headers={"X-API-Key": "wrong"})).status_code == 401


async def test_successful_continuation_preserves_history_and_counts_both_requests(api) -> None:
    async with api() as (client, transport, _):
        transport.tools = True
        initial = (await client.post("/v1/chat/completions", json=user())).json()
        transport.tools = False
        result = await client.post("/v1/chat/completions", json=continuation(initial["run_id"]))
        assert result.status_code == 200, result.text
        assert result.json()["budget"]["consumed_requests"] == 2
        assert result.json()["budget"]["settled_tokens"] == 24
        assert result.json()["run_id"] == initial["run_id"]
        assert [message["role"] for message in transport.requests[-1]["messages"]] == [
            "user",
            "assistant",
            "tool",
        ]
        assert (
            await client.post("/v1/chat/completions", json=continuation(initial["run_id"]))
        ).status_code == 409


async def test_same_run_concurrency_rejects_before_mutation_or_transport(api) -> None:
    async with api() as (client, transport, _):
        transport.tools = True
        initial = (await client.post("/v1/chat/completions", json=user())).json()
        transport.tools, transport.wait = False, True
        transport.started.clear()
        pending = asyncio.create_task(
            client.post("/v1/chat/completions", json=continuation(initial["run_id"]))
        )
        await transport.started.wait()
        duplicate = await client.post("/v1/chat/completions", json=continuation(initial["run_id"]))
        assert duplicate.status_code == 409
        assert len(transport.requests) == 2
        for route in ("/v1/chat/history",):
            assert (
                await client.delete(route, params={"run_id": initial["run_id"]})
            ).status_code == 409
        transport.release.set()
        assert (await pending).status_code == 200


async def test_history_deletion_does_not_reset_pending_budget(api) -> None:
    settings = Settings.model_validate({"usage": {"limits": {"max_requests": 1}}})
    async with api(settings) as (client, transport, _):
        transport.tools = True
        initial = (await client.post("/v1/chat/completions", json=user())).json()
        assert (await client.delete("/v1/chat/history")).status_code == 200
        assert (await client.get("/v1/chat/history")).json() == []
        assert (await client.get("/v1/usage")).json()["budget"]["consumed_requests"] == 1
        assert (
            await client.post("/v1/chat/completions", json=continuation(initial["run_id"]))
        ).status_code == 429
        assert len(transport.requests) == 1


async def test_invalid_tool_ids_and_replaced_history_do_not_consume_authority(api) -> None:
    async with api() as (client, transport, _):
        transport.tools = True
        initial = (await client.post("/v1/chat/completions", json=user())).json()
        payload = continuation(initial["run_id"])
        invalid = [
            {**payload, "messages": payload["messages"] * 2},
            {**payload, "messages": [{"role": "tool", "content": "x", "tool_call_id": "wrong"}]},
            {
                **payload,
                "messages": [{"role": "user", "content": "replaced"}, *payload["messages"]],
            },
        ]
        for request in invalid:
            assert (await client.post("/v1/chat/completions", json=request)).status_code == 422
        assert len(transport.requests) == 1
        transport.tools = False
        assert (await client.post("/v1/chat/completions", json=payload)).status_code == 200


@pytest.mark.parametrize("limits", [{"max_tokens": 0}, {"max_seconds": 0}, {"max_cost": "0"}])
async def test_other_zero_caps_are_not_falsey_defaults(api, limits) -> None:
    settings = Settings.model_validate({"usage": {"limits": limits}})
    async with api(settings) as (client, transport, _):
        assert (await client.post("/v1/chat/completions", json=user())).status_code == 429
        assert not transport.requests


async def test_price_snapshot_remains_exact_and_separate_from_reported_billing(api) -> None:
    settings = Settings.model_validate(
        {
            "usage": {
                "prices": [
                    {
                        "provider": "openai-compatible",
                        "model": "test-model",
                        "currency": "EUR",
                        "input_per_1k": "1.000000000000000000000000000001",
                        "output_per_1k": "2",
                    }
                ]
            }
        }
    )
    async with api(settings) as (client, _, _):
        response = (await client.post("/v1/chat/completions", json=user())).json()
        money = response["budget"]["money"][0]
        assert money["currency"] == "EUR"
        assert money["settled_estimated_cost"] == "0.01400000000000000000000000000001"
        assert money["reported_cost"] is None
        assert (await client.get("/v1/usage")).json()["total_cost"] is None


async def test_uninstrumented_provider_with_limits_refuses_dispatch(api) -> None:
    settings = Settings.model_validate({"usage": {"limits": {"max_requests": 1}}})
    async with api(settings) as (client, transport, runtime):
        runtime.agent.provider.supports_run_budget = False
        response = await client.post("/v1/chat/completions", json=user())
        assert response.status_code == 503
        assert not transport.requests


async def test_completed_eviction_never_resets_old_ids_and_pending_runs_stay(api) -> None:
    async with api() as (client, transport, runtime):
        runtime.chat_runs.max_runs = 1
        old = (await client.post("/v1/chat/completions", json=user())).json()["run_id"]
        transport.tools = True
        waiting = (await client.post("/v1/chat/completions", json=user("next"))).json()["run_id"]
        assert (await client.get("/v1/usage", params={"run_id": old})).status_code == 404
        assert (
            await client.post("/v1/chat/completions", json=continuation(old))
        ).status_code == 404
        assert (await client.post("/v1/chat/completions", json=user("overflow"))).status_code == 503
        assert (await client.get("/v1/usage", params={"run_id": waiting})).status_code == 200
        assert len(transport.requests) == 2


async def test_stream_close_retains_dispatched_hold_and_releases_claim(api) -> None:
    from henchman.api.endpoints.chat import ChatRequest, _stream_response

    async with api() as (_, transport, runtime):
        response = _stream_response(ChatRequest.model_validate(user()), "unauthenticated-local")
        iterator = response.body_iterator
        start = json.loads((await anext(iterator)).removeprefix("data: "))
        run_id = start["data"]["run_id"]
        transport.wait = True
        advancing = asyncio.create_task(anext(iterator))
        await transport.started.wait()
        advancing.cancel()
        with pytest.raises(asyncio.CancelledError):
            await advancing
        await iterator.aclose()
        run = runtime.chat_runs.find("unauthenticated-local", run_id)
        assert not run.busy and run.interrupted
        assert run.budget()["consumed_requests"] == 1
        assert run.budget()["unknown_dispatched_requests"] == 1
        assert run.budget()["held_tokens"] > 0


async def test_summary_uses_same_scope_as_api_turn(api, monkeypatch) -> None:
    from henchman.core.agent import Agent
    from henchman.utils.compaction import MessageSummarizer

    async def prepare_summary(self):
        await MessageSummarizer(self.provider).summarize(self.messages)
        return await original(self)

    original = Agent._prepare_stream_context
    monkeypatch.setattr(Agent, "_prepare_stream_context", prepare_summary)
    settings = Settings.model_validate({"usage": {"limits": {"max_requests": 1}}})
    async with api(settings) as (client, transport, _):
        response = await client.post("/v1/chat/completions", json=user())
        assert response.status_code == 429
        assert len(transport.requests) == 1
        assert response.json()["details"]["budget"]["settled_tokens"] == 12


async def test_usage_does_not_label_missing_usage_as_zero(api) -> None:
    async with api() as (client, transport, _):
        transport.usage = False
        response = await client.post("/v1/chat/completions", json=user())
        assert response.status_code == 200
        report = (await client.get("/v1/usage")).json()
        assert report["total_tokens"] is None
        assert report["budget"]["unknown_dispatched_requests"] == 1
        assert report["budget"]["held_tokens"] > 0


async def test_lifespan_restart_does_not_accept_previous_run_identity(api) -> None:
    async with api() as (client, transport, runtime):
        transport.tools = True
        previous = (await client.post("/v1/chat/completions", json=user())).json()["run_id"]
    assert runtime.chat_runs is None
    async with api() as (client, transport, _):
        assert (await client.post("/v1/chat/completions", json=continuation(previous))).status_code == 404
        assert not transport.requests


async def test_api_factory_binds_restricted_tool_settings(api, tmp_path) -> None:
    from henchman.tools.builtins.file_read import ReadFileTool

    protected = tmp_path / "data"
    protected.write_text("protected contents")
    settings = Settings.model_validate({"tools": {"filesystem_read_roots": []}})
    async with api(settings) as (client, _, runtime):
        assert (await client.post("/v1/chat/completions", json=user())).status_code == 200
        run = runtime.chat_runs.find("unauthenticated-local")
        run.agent.tool_registry.register(ReadFileTool())
        result = await run.agent.tool_registry.execute("read_file", {"path": str(protected)})
        assert not result.success
        assert "protected contents" not in result.content
