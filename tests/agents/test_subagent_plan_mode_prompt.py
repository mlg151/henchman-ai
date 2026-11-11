"""Dynamic subagents inherit the active Plan Mode boundary in their prompt (#18).

Scoped subagent registries enforce the parent's plan-mode gate at call time,
but the child's system prompt must also announce the read-only boundary so
the model plans instead of attempting writes. The prompt is inherited only
while the boundary is in force.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any

import pytest

from henchman.agents.orchestrator import Orchestrator
from henchman.cli.commands.plan import PLAN_MODE_PROMPT
from henchman.config.schema import Settings
from henchman.providers.base import FinishReason, Message, StreamChunk, ToolCall
from henchman.providers.ollama import OllamaProvider
from henchman.tools.registry import ToolRegistry


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


async def _spawn_and_collect_system_prompt(
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[Orchestrator, str]:
    """Spawn one dynamic subagent and return its delivered system prompt."""
    observed: list[str] = []
    started = asyncio.Event()

    async def stream(messages: list[Message], **kwargs: Any) -> AsyncIterator[StreamChunk]:
        del kwargs
        if (messages[0].content or "").startswith("custom child"):
            observed.append(messages[0].content or "")
            started.set()
            yield _response("done")
            return
        yield _response("done")

    provider = OllamaProvider()
    monkeypatch.setattr(provider, "chat_completion_stream", stream)
    registry = ToolRegistry()
    orch = Orchestrator(provider, tool_registry=registry, settings=Settings(agents={"allow_delegation": True}))
    orch.subagents.spawn("task", role="custom", system_prompt="custom child", tools=[])
    try:
        await asyncio.wait_for(started.wait(), 2)
        await asyncio.wait_for(orch.subagents.wait_for_notification(), 2)
        assert observed, "child stream was never invoked"
        return orch, observed[0]
    except BaseException:
        await orch.aclose()
        raise


async def test_dynamic_subagent_prompt_inherits_active_plan_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A child spawned under an active plan boundary announces the boundary."""
    observed: list[str] = []
    started = asyncio.Event()

    async def stream(messages: list[Message], **kwargs: Any) -> AsyncIterator[StreamChunk]:
        del kwargs
        if (messages[0].content or "").startswith("custom child"):
            observed.append(messages[0].content or "")
            started.set()
            yield _response("done")
            return
        yield _response("done")

    provider = OllamaProvider()
    monkeypatch.setattr(provider, "chat_completion_stream", stream)
    registry = ToolRegistry()
    registry.set_plan_mode(enabled=True)
    orch = Orchestrator(provider, tool_registry=registry, settings=Settings(agents={"allow_delegation": True}))
    orch.subagents.spawn("task", role="custom", system_prompt="custom child", tools=[])
    try:
        await asyncio.wait_for(started.wait(), 2)
        await asyncio.wait_for(orch.subagents.wait_for_notification(), 2)
        assert observed, "child stream was never invoked"
        assert PLAN_MODE_PROMPT in observed[0]
    finally:
        await orch.aclose()


async def test_dynamic_subagent_prompt_omits_plan_mode_when_boundary_inactive(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No plan-mode text is injected while the parent boundary is inactive."""
    _orch, system_prompt = await _spawn_and_collect_system_prompt(monkeypatch)
    assert PLAN_MODE_PROMPT not in system_prompt
