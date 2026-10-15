"""Primary coding-agent scope and background orchestration integration."""

import asyncio
import json
from collections.abc import AsyncIterator
from functools import partial
from typing import Any
from unittest.mock import MagicMock

import pytest

from henchman.agents.orchestrator import CompletionStatus, Orchestrator
from henchman.cli.commands.discovery_capabilities import classify_registered_tool
from henchman.config.schema import AgentConfig, Settings
from henchman.core.events import EventType
from henchman.providers.base import FinishReason, Message, ModelProvider, StreamChunk, ToolCall
from henchman.providers.ollama import OllamaProvider
from henchman.tools.base import Tool, ToolKind, ToolResult
from henchman.tools.registry import ToolRegistry


class _WorkspaceTool(Tool):
    def __init__(self, name: str) -> None:
        self._name = name

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return "Workspace operation for scope verification."

    @property
    def parameters(self) -> dict[str, object]:
        return {"type": "object", "properties": {}}

    @property
    def kind(self) -> ToolKind:
        return ToolKind.READ

    async def execute(self, **params: object) -> ToolResult:
        return ToolResult(content="ok")


def _provider() -> MagicMock:
    provider = MagicMock(spec=ModelProvider)
    provider.estimate_input_tokens.side_effect = partial(
        ModelProvider.estimate_input_tokens, provider
    )
    provider.prepare_output_budget.side_effect = partial(
        ModelProvider.prepare_output_budget, provider
    )
    return provider


def test_primary_has_full_live_workspace_tools() -> None:
    registry = ToolRegistry()
    registry.register(_WorkspaceTool("write_file"))
    registry.register(_WorkspaceTool("custom_diagnostics"))
    orch = Orchestrator(default_provider=_provider(), tool_registry=registry)
    assert orch.tech_lead.tool_registry.get("write_file") is registry.get("write_file")
    assert orch.tech_lead.tool_registry.get("custom_diagnostics") is registry.get(
        "custom_diagnostics"
    )
    registry.register(_WorkspaceTool("late_mcp_tool"))
    assert orch.tech_lead.tool_registry.get("late_mcp_tool") is registry.get("late_mcp_tool")
    assert orch.tech_lead.tool_registry.get("invoke_subagent") is not None
    assert orch.tech_lead.tool_registry.get("manage_subagents") is not None


def test_explicit_primary_allowlist_remains_a_boundary() -> None:
    settings = Settings()
    settings.agents.agents["tech_lead"] = AgentConfig(
        name="Restricted primary",
        role="tech_lead",
        description="Explicit scope",
        tools=["read_file"],
    )
    registry = ToolRegistry()
    registry.register(_WorkspaceTool("read_file"))
    registry.register(_WorkspaceTool("write_file"))
    orch = Orchestrator(default_provider=_provider(), tool_registry=registry, settings=settings)
    assert orch.tech_lead.tool_registry.get("read_file") is not None
    assert orch.tech_lead.tool_registry.get("write_file") is None
    assert orch.tech_lead.tool_registry.get("invoke_subagent") is None


def test_subagent_discovery_requires_runtime_tools_and_retains_binding_caveat() -> None:
    names = ("invoke_subagent", "manage_subagents", "send_message")
    for name in names:
        missing = classify_registered_tool(name, registered_tool_names=(name,))
        assert missing is not None and missing.classification == "unavailable"
        registered = classify_registered_tool(name, registered_tool_names=names)
        assert registered is not None and registered.classification == "runtime-dependent"
        assert "bound orchestrator" in registered.detail


@pytest.mark.asyncio
async def test_concurrent_subagents_reactively_resume_primary_and_preserve_transcript(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    started: set[str] = set()
    both_started = asyncio.Event()
    parent_calls = 0

    async def stream(messages: list[Message], **kwargs: Any) -> AsyncIterator[StreamChunk]:
        nonlocal parent_calls
        system = messages[0].content or ""
        if system.startswith("child "):
            started.add(system)
            if len(started) == 2:
                both_started.set()
            await both_started.wait()
            assert {tool.name for tool in kwargs.get("tools", [])} == {"read_file"}
            yield StreamChunk(content=f"Result from {system}", finish_reason=FinishReason.STOP)
            return
        parent_calls += 1
        if parent_calls == 1:
            yield StreamChunk(
                tool_calls=[
                    ToolCall(
                        id=f"launch-{i}",
                        name="invoke_subagent",
                        arguments={
                            "task": f"Review part {i}",
                            "role": "custom reviewer",
                            "system_prompt": f"child {i}",
                            "tools": ["read_file"],
                        },
                    )
                    for i in range(2)
                ],
                finish_reason=FinishReason.TOOL_CALLS,
            )
        elif parent_calls == 2:
            yield StreamChunk(content="I continued my own work.", finish_reason=FinishReason.STOP)
        else:
            updates = "\n".join(
                message.content or "" for message in messages if message.role == "user"
            )
            assert "Result from child" in updates
            yield StreamChunk(
                content="Reviewed background results.", finish_reason=FinishReason.STOP
            )

    provider = OllamaProvider()
    monkeypatch.setattr(provider, "chat_completion_stream", stream)
    registry = ToolRegistry()
    registry.register(_WorkspaceTool("read_file"))
    orch = Orchestrator(provider, tool_registry=registry)
    registry.add_auto_approve_policy("invoke_subagent")
    try:
        events = await asyncio.wait_for(_collect(orch, "Review two parts"), timeout=3)
        assert len(started) == 2
        assert all(record.status == "done" for record in orch.subagents.list())
        assert any(event.type == EventType.AGENT_MESSAGE for event in events)
        assert parent_calls >= 3
        assert orch.last_completion_status == CompletionStatus.COMPLETED
        transcript = orch.tech_lead.current_turn_messages
        assert transcript[0].content == "Review two parts"
        assert len([message for message in transcript if message.role == "tool"]) == 2
        assert any(
            "Reviewed background results" in (message.content or "") for message in transcript
        )
    finally:
        await orch.aclose()


async def _collect(orch: Orchestrator, prompt: str) -> list[Any]:
    return [event async for event in orch.run(prompt)]


@pytest.mark.asyncio
async def test_child_question_and_parent_answer_use_real_queued_messages(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    parent_calls = 0
    answered = False

    async def stream(messages: list[Message], **kwargs: Any) -> AsyncIterator[StreamChunk]:
        nonlocal parent_calls, answered
        del kwargs
        if messages[0].content == "question child":
            answers = [message.content for message in messages if message.role == "tool"]
            if not answers:
                yield StreamChunk(
                    tool_calls=[
                        ToolCall(
                            id="ask",
                            name="ask_user",
                            arguments={"question": "Which file?"},
                        )
                    ],
                    finish_reason=FinishReason.TOOL_CALLS,
                )
            else:
                assert answers[-1] == "app.py"
                answered = True
                yield StreamChunk(content="Reviewed app.py", finish_reason=FinishReason.STOP)
            return
        parent_calls += 1
        if parent_calls == 1:
            yield StreamChunk(
                tool_calls=[
                    ToolCall(
                        id="launch",
                        name="invoke_subagent",
                        arguments={
                            "task": "Review a file",
                            "role": "review",
                            "system_prompt": "question child",
                            "tools": ["ask_user"],
                        },
                    )
                ],
                finish_reason=FinishReason.TOOL_CALLS,
            )
        elif messages[-1].role == "user" and "Which file?" in (messages[-1].content or ""):
            updates = json.loads((messages[-1].content or "").split("\n")[1])
            yield StreamChunk(
                tool_calls=[
                    ToolCall(
                        id="answer",
                        name="send_message",
                        arguments={
                            "conversation_id": updates[0]["conversation_id"],
                            "message": "app.py",
                        },
                    )
                ],
                finish_reason=FinishReason.TOOL_CALLS,
            )
        else:
            yield StreamChunk(content="Waiting or reviewed.", finish_reason=FinishReason.STOP)

    from henchman.tools.builtins.ask_user import AskUserTool

    provider = OllamaProvider()
    monkeypatch.setattr(provider, "chat_completion_stream", stream)
    registry = ToolRegistry()
    registry.register(AskUserTool())
    orch = Orchestrator(provider, tool_registry=registry)
    for name in ("invoke_subagent", "send_message"):
        registry.add_auto_approve_policy(name)
    try:
        await asyncio.wait_for(_collect(orch, "Review requested file"), 3)
        assert answered
        assert orch.subagents.list()[0].status == "done"
    finally:
        await orch.aclose()
