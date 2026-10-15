"""Runtime boundaries for dynamic nesting, exact scopes, and cancellation."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any

import pytest

from henchman.agents.orchestrator import Orchestrator
from henchman.config.schema import AgentConfig, Settings
from henchman.core.events import EventType
from henchman.providers.base import FinishReason, Message, StreamChunk, ToolCall
from henchman.providers.ollama import OllamaProvider
from henchman.tools.base import Tool, ToolKind, ToolResult
from henchman.tools.registry import ToolRegistry


class _NamedTool(Tool):
    def __init__(self, name: str, kind: ToolKind = ToolKind.READ) -> None:
        self._name = name
        self._kind = kind

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return "Test workspace tool."

    @property
    def kind(self) -> ToolKind:
        return self._kind

    async def execute(self, **params: object) -> ToolResult:
        return ToolResult(content="ok")


def _launch(prompt: str, tools: list[str], call_id: str = "launch") -> StreamChunk:
    return StreamChunk(
        tool_calls=[
            ToolCall(
                id=call_id,
                name="invoke_subagent",
                arguments={
                    "task": "delegated task",
                    "role": "custom",
                    "system_prompt": prompt,
                    "tools": tools,
                },
            )
        ],
        finish_reason=FinishReason.TOOL_CALLS,
    )


def _response(text: str) -> StreamChunk:
    return StreamChunk(content=text, finish_reason=FinishReason.STOP)


async def test_dynamic_tools_are_exactly_the_explicit_subset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    declared: set[str] = set()

    async def stream(messages: list[Message], **kwargs: Any) -> AsyncIterator[StreamChunk]:
        del messages
        declared.update(tool.name for tool in kwargs.get("tools", []))
        yield _response("done")

    provider = OllamaProvider()
    monkeypatch.setattr(provider, "chat_completion_stream", stream)
    registry = ToolRegistry()
    for name in ("shell", "goal_status", "task_stop"):
        registry.register(_NamedTool(name))
    orch = Orchestrator(provider, tool_registry=registry)
    try:
        orch.subagents.spawn("task", role="custom", system_prompt="custom", tools=["shell"])
        await asyncio.wait_for(orch.subagents.wait_for_notification(), 1)
        assert declared == {"shell"}
    finally:
        await orch.aclose()


async def test_restricted_static_agent_cannot_delegate_primary_tools(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def stream(messages: list[Message], **kwargs: Any) -> AsyncIterator[StreamChunk]:
        del kwargs
        if messages[0].content == "restricted static" and not any(
            message.role == "tool" for message in messages
        ):
            yield _launch("unauthorized child", ["shell"])
        else:
            yield _response("done")

    provider = OllamaProvider()
    monkeypatch.setattr(provider, "chat_completion_stream", stream)
    registry = ToolRegistry()
    registry.register(_NamedTool("shell"))
    registry.add_auto_approve_policy("invoke_subagent")
    settings = Settings()
    settings.agents.agents["coder"] = AgentConfig(
        name="Restricted",
        role="coder",
        description="Restricted static agent",
        system_prompt="restricted static",
        tools=["invoke_subagent"],
        auto_approve=["invoke_subagent"],
    )
    orch = Orchestrator(provider, tool_registry=registry, settings=settings)
    try:
        events = [event async for event in orch.run_direct("coder", "task")]
        result = next(event for event in events if event.type == EventType.TOOL_CALL_RESULT)
        assert result.data["success"] is False
        assert orch.subagents.list() == []
    finally:
        await orch.aclose()


async def test_nested_results_reactively_resume_each_parent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def stream(messages: list[Message], **kwargs: Any) -> AsyncIterator[StreamChunk]:
        del kwargs
        system = messages[0].content or ""
        tool_results = [message for message in messages if message.role == "tool"]
        if system == "leaf":
            yield _response("Leaf result")
        elif system == "middle":
            if not tool_results:
                yield _launch("leaf", [], "nested")
            elif messages[-1].role == "user" and "Leaf result" in (messages[-1].content or ""):
                yield _response("Middle accepted nested result")
            else:
                yield _response("Middle continues")
        elif not tool_results:
            yield _launch("middle", ["invoke_subagent"])
        else:
            yield _response("Primary accepted result")

    provider = OllamaProvider()
    monkeypatch.setattr(provider, "chat_completion_stream", stream)
    registry = ToolRegistry()
    registry.add_auto_approve_policy("invoke_subagent")
    orch = Orchestrator(provider, tool_registry=registry)
    try:
        async with asyncio.timeout(3):
            events = [event async for event in orch.run("Run nested work")]
        assert len(orch.subagents.list()) == 2
        assert all(record.status == "done" for record in orch.subagents.list())
        assert any(
            event.type == EventType.AGENT_MESSAGE
            and "Middle accepted nested result" in event.data["message"]
            for event in events
        )
    finally:
        await orch.aclose()


async def test_cancel_primary_joins_child_and_releases_agent_claims(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    child_started = asyncio.Event()

    async def stream(messages: list[Message], **kwargs: Any) -> AsyncIterator[StreamChunk]:
        del kwargs
        if messages[0].content == "blocked child":
            child_started.set()
            await asyncio.Event().wait()
        elif not any(message.role == "tool" for message in messages):
            yield _launch("blocked child", [])
        else:
            yield _response("Working independently")

    provider = OllamaProvider()
    monkeypatch.setattr(provider, "chat_completion_stream", stream)
    registry = ToolRegistry()
    registry.add_auto_approve_policy("invoke_subagent")
    orch = Orchestrator(provider, tool_registry=registry)

    async def collect() -> None:
        async for _event in orch.run("Launch work"):
            pass

    task = asyncio.create_task(collect())
    try:
        await asyncio.wait_for(child_started.wait(), 1)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert orch.subagents.list()[0].cancelled
        assert not orch.subagents.has_running_work()
        assert orch.pool._execution_claims == {}
    finally:
        await orch.aclose()


async def test_shared_registry_keeps_managers_and_primary_scopes_independent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def stream(messages: list[Message], **kwargs: Any) -> AsyncIterator[StreamChunk]:
        del messages, kwargs
        yield _response("done")

    provider = OllamaProvider()
    monkeypatch.setattr(provider, "chat_completion_stream", stream)
    registry = ToolRegistry()
    registry.register(_NamedTool("shell"))
    unrestricted = Orchestrator(provider, tool_registry=registry)
    settings = Settings()
    settings.agents.agents["tech_lead"] = AgentConfig(
        name="Restricted primary",
        role="tech_lead",
        description="Explicit scope",
        tools=["invoke_subagent"],
    )
    restricted = Orchestrator(provider, tool_registry=registry, settings=settings)
    arguments: dict[str, object] = {
        "task": "task",
        "role": "custom",
        "system_prompt": "custom",
        "tools": ["shell"],
    }
    try:
        launched = await unrestricted.tech_lead.tool_registry.execute("invoke_subagent", arguments)
        assert launched.success, launched.content
        denied = await restricted.tech_lead.tool_registry.execute("invoke_subagent", arguments)
        assert not denied.success
        await asyncio.wait_for(unrestricted.subagents.wait_for_notification(), 1)
        assert len(unrestricted.subagents.list()) == 1
        assert restricted.subagents.list() == []
    finally:
        await unrestricted.aclose()
        await restricted.aclose()
