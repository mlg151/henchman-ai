"""The team evaluation profile uses production orchestration and provenance."""

import asyncio
import json
from collections.abc import AsyncGenerator, Iterator
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import pytest
from evals.helpers import EvalTestRig, MockProvider

from henchman.config.schema import Settings
from henchman.core.agent_config import AgentConfig
from henchman.core.events import AgentEvent, EventType
from henchman.providers.base import Message, StreamChunk, ToolCall, ToolDeclaration
from henchman.utils.validation import validate_message_sequence


@pytest.fixture
def make_rig() -> Iterator[Any]:
    rigs: list[EvalTestRig] = []

    def make(**kwargs: Any) -> EvalTestRig:
        rig = EvalTestRig(
            provider=kwargs.pop("provider", MockProvider()),
            profile=kwargs.pop("profile", "team"), **kwargs,
        )
        rigs.append(rig)
        rig.setup("team-profile")
        return rig

    yield make
    for rig in reversed(rigs):
        rig.cleanup()


@pytest.mark.parametrize("kwargs", [{"config": AgentConfig()}, {"system_prompt": ""}, {"system_prompt": "custom"}])
def test_team_rejects_conflicting_single_agent_configuration(kwargs: dict[str, Any]) -> None:
    with pytest.raises(ValueError, match="team.*(config|prompt)"):
        EvalTestRig(provider=MockProvider(), profile="team", **kwargs)


@pytest.mark.parametrize("profile", ["basic", "engineer"])
def test_settings_are_only_accepted_for_team(profile: str) -> None:
    with pytest.raises(ValueError, match="settings.*team"):
        EvalTestRig(provider=MockProvider(), profile=profile, settings=Settings())


def test_team_uses_copied_settings_production_scopes_and_redacted_metadata(make_rig: Any) -> None:
    settings = Settings()
    settings.providers.openrouter["api_key"] = "NEVER_EXPOSE_KEY"
    settings.agents.max_delegation_depth = 2
    settings.agents.max_delegation_turns = 7
    settings.agents.max_delegation_retries = 1
    settings.context.max_tokens = 12000
    rig = make_rig(settings=settings)
    orch = rig.orchestrator
    assert orch.settings is not settings
    assert orch.settings.agents.max_delegation_turns == 7
    assert orch.settings.agents.max_delegation_depth == 2
    assert orch.settings.agents.max_delegation_retries == 1
    assert orch.tech_lead is orch.pool.get_agent("tech_lead")
    assert orch.tech_lead.tool_registry.get("edit_file") is None
    assert orch.pool.get_agent("engineer").tool_registry.get("edit_file") is not None
    metadata = rig.profile_metadata
    assert metadata["profile"] == "team"
    assert metadata["scope"] == "team"
    assert metadata["roles_preinitialized"] is True
    assert {"tech_lead", "engineer", "explorer"} <= metadata["roles"].keys()
    for role in metadata["roles"].values():
        assert role["provider"] == "mock"
        assert isinstance(role["model"], str)
        assert role["context_window"] == 12000
        assert role["output_tokens"] > 0
        assert role["prompt_chars"] > 0
        assert len(role["prompt_sha256"]) == 64
        assert "system_prompt" not in role
    assert "NEVER_EXPOSE_KEY" not in json.dumps(metadata)
    metadata["roles"]["engineer"]["tool_names"].clear()
    assert rig.profile_metadata["roles"]["engineer"]["tool_names"]
    orch.settings.agents.max_delegation_turns = 99
    assert settings.agents.max_delegation_turns == 7


def test_orchestrator_property_rejects_nonteam_and_uninitialized() -> None:
    with pytest.raises(RuntimeError, match="team"):
        _ = EvalTestRig(provider=MockProvider(), profile="basic").orchestrator
    with pytest.raises(RuntimeError, match="set up"):
        _ = EvalTestRig(provider=MockProvider(), profile="team").orchestrator


def delegation() -> list[ToolCall]:
    return [ToolCall("same", "delegate_task", {
        "agent": "engineer", "task": "Read and update source.txt",
        "completion_requirement": "actions",
    })]


async def test_team_logs_actual_delegation_and_child_tools_in_request_order(make_rig: Any) -> None:
    provider = MockProvider([
        delegation(),
        [ToolCall("same", "read_file", {"path": "source.txt"})],
        [ToolCall("write", "write_file", {"path": "source.txt", "content": "updated"})],
        "CHILD_ONLY", "LEADER_FINAL",
    ])
    rig = make_rig(provider=provider)
    rig.create_file("source.txt", "original")
    result = await rig.run("Delegate the update", max_iterations=4, timeout=5)
    assert result.success and result.error is None
    assert result.final_response == "LEADER_FINAL"
    assert rig.read_file("source.txt") == "updated"
    assert [(log.source_agent, log.tool_call_id, log.tool_name) for log in result.tool_logs] == [
        ("tech_lead", "same", "delegate_task"),
        ("engineer", "same", "read_file"),
        ("engineer", "write", "write_file"),
    ]
    assert all(log.success for log in result.tool_logs)
    assert result.tool_logs[1].arguments == {"path": "source.txt"}
    assert "original" in result.tool_logs[1].result
    delegation_log, read, write = result.tool_logs
    assert read.result_index is not None and write.request_index is not None
    assert read.result_index < write.request_index
    assert delegation_log.result_index is not None and write.result_index is not None
    assert delegation_log.result_index > write.result_index
    assert result.tokens_in is result.tokens_out is None
    assert rig.get_tool_calls("delegate_task") == result.tool_logs[:1]
    assert len([e for e in result.events if e.type == EventType.FINISHED]) == 1
    for role in ("tech_lead", "engineer"):
        validate_message_sequence(rig.orchestrator.pool.get_agent(role).messages)


async def test_batch_request_order_does_not_imply_inspection_completed(make_rig: Any) -> None:
    provider = MockProvider([
        delegation(),
        [
            ToolCall("read", "read_file", {"path": "source.txt"}),
            ToolCall("write", "write_file", {"path": "source.txt", "content": "new"}),
        ],
        "Child finished", "Leader finished",
    ])
    rig = make_rig(provider=provider)
    rig.create_file("source.txt", "original")
    result = await rig.run("Update the file", timeout=5)
    assert result.success
    _delegation, read, write = result.tool_logs
    assert read.request_index is not None and read.result_index is not None
    assert write.request_index is not None
    assert read.request_index < write.request_index < read.result_index


async def test_failed_tool_result_is_retained_with_its_actual_actor(make_rig: Any) -> None:
    provider = MockProvider([
        delegation(),
        [ToolCall("reused", "read_file", {"path": "missing.txt"})],
        [ToolCall("reused", "write_file", {"path": "missing.txt", "content": "new"})],
        "Child finished", "Leader finished",
    ])
    rig = make_rig(provider=provider)
    result = await rig.run("Recover missing file", timeout=5)
    _delegation, failed, recovered = result.tool_logs
    assert failed.source_agent == recovered.source_agent == "engineer"
    assert failed.tool_call_id == recovered.tool_call_id == "reused"
    assert not failed.success and recovered.success
    assert failed.result_index is not None and recovered.request_index is not None
    assert failed.result_index < recovered.request_index


class FailingOnceProvider(MockProvider):
    def __init__(self) -> None:
        super().__init__([
            [ToolCall("read", "read_file", {"path": "source.txt"})], "Child recovered",
        ])
        self.failed = False

    async def chat_completion_stream(
        self, messages: list[Message], tools: list[ToolDeclaration] | None = None,
        temperature: float | None = None, max_tokens: int | None = None,
        **kwargs: Any,
    ) -> AsyncGenerator[StreamChunk, None]:
        if not self.failed:
            self.failed = True
            raise RuntimeError("Recoverable child failure")
        async for chunk in super().chat_completion_stream(
            messages, tools, temperature, max_tokens, **kwargs
        ):
            yield chunk


async def test_recovered_child_error_is_diagnostic_not_root_failure(make_rig: Any) -> None:
    settings = Settings()
    settings.agents.max_delegation_retries = 1
    rig = make_rig(provider=MockProvider([delegation(), "LEADER_RECOVERED"]), settings=settings)
    rig.orchestrator.pool.get_agent("engineer").provider = FailingOnceProvider()
    rig.create_file("source.txt", "source")
    result = await rig.run("Delegate inspection", timeout=5)
    assert result.success and result.error is None
    assert result.final_response == "LEADER_RECOVERED"
    assert any("Recoverable child failure" in error for error in result.diagnostics)
    assert any(event.type == EventType.ERROR for event in result.events)


async def test_root_failure_remains_failed(make_rig: Any) -> None:
    rig = make_rig(provider=FailingOnceProvider())
    result = await rig.run("Fail this turn", timeout=5)
    assert not result.success
    assert result.error
    assert result.tokens_in is result.tokens_out is None


async def test_iteration_limit_applies_to_all_roles_and_restores_configuration(make_rig: Any) -> None:
    rig = make_rig(provider=MockProvider([delegation()]))
    agents = {
        role: rig.orchestrator.pool.get_agent(role)
        for role, config in rig.orchestrator.pool.configs.items() if config.enabled
    }
    limits = {role: agent.base_tool_iterations for role, agent in agents.items()}
    result = await rig.run("Delegate", max_iterations=0, timeout=5)
    assert not result.success
    assert not any(event.type == EventType.AGENT_DELEGATED for event in result.events)
    applied = rig.profile_metadata["last_run_limits"]
    assert all(role["base_tool_iterations"] == 0 for role in applied["roles"].values())
    assert applied["delegation"]["max_turns"] == rig.orchestrator.settings.agents.max_delegation_turns
    assert {role: agent.base_tool_iterations for role, agent in agents.items()} == limits


async def test_specialist_cannot_exceed_evaluation_tool_round_limit(make_rig: Any) -> None:
    settings = Settings()
    settings.agents.max_delegation_retries = 0
    provider = MockProvider([
        delegation(),
        [ToolCall("first", "write_file", {"path": "first.txt", "content": "one"})],
        [ToolCall("second", "write_file", {"path": "second.txt", "content": "two"})],
        "Leader received the failure",
    ])
    rig = make_rig(provider=provider, settings=settings)
    result = await rig.run("Delegate bounded edits", max_iterations=1, timeout=5)
    assert rig.file_exists("first.txt")
    assert not rig.file_exists("second.txt")
    second = next(log for log in result.tool_logs if log.tool_call_id == "second")
    assert second.source_agent == "engineer" and not second.success
    assert "iteration limit" in second.result.lower()
    assert rig.profile_metadata["last_run_limits"]["roles"]["engineer"] == {
        "base_tool_iterations": 1,
    }


class HeldProvider(MockProvider):
    def __init__(self) -> None:
        super().__init__()
        self.waiting = asyncio.Event()
        self.closed = asyncio.Event()

    async def chat_completion_stream(
        self, messages: list[Message], tools: list[ToolDeclaration] | None = None,
        temperature: float | None = None, max_tokens: int | None = None,
        **kwargs: Any,
    ) -> AsyncGenerator[StreamChunk, None]:
        try:
            self.waiting.set()
            await asyncio.Event().wait()
            yield StreamChunk()
        finally:
            self.closed.set()


async def test_timeout_closes_team_stream_and_allows_reuse(make_rig: Any) -> None:
    provider = HeldProvider()
    rig = make_rig(provider=provider)
    result = await rig.run("Wait", timeout=0.05, max_iterations=1)
    assert not result.success and "timed out" in (result.error or "")
    assert provider.closed.is_set()
    rig.orchestrator.tech_lead.provider = MockProvider(["Recovered"])
    assert (await rig.run("Retry", timeout=5)).success


async def test_cancellation_closes_team_stream_and_cleanup_restores_workspace() -> None:
    original = Path.cwd()
    provider = HeldProvider()
    rig = EvalTestRig(provider=MockProvider([delegation()]), profile="team")
    rig.setup("cancel-team")
    rig.orchestrator.pool.get_agent("engineer").provider = provider
    workspace = rig.test_dir
    task = asyncio.create_task(rig.run("Wait", timeout=5))
    try:
        await asyncio.wait_for(provider.waiting.wait(), timeout=3)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert provider.closed.is_set()
        with pytest.raises(AssertionError):
            rig.assert_successful_runs()
    finally:
        rig.cleanup()
    assert Path.cwd() == original
    assert not workspace.exists()


def test_team_setup_error_restores_workspace(monkeypatch: pytest.MonkeyPatch) -> None:
    from henchman.cli.tool_manager import ToolManager

    original = Path.cwd()
    rig = EvalTestRig(provider=MockProvider(), profile="team")

    def fail(_self: ToolManager) -> None:
        raise RuntimeError("Registration failed")

    monkeypatch.setattr(ToolManager, "register_builtin_tools", fail)
    with pytest.raises(RuntimeError, match="Registration failed"):
        rig.setup("failed-team")
    assert Path.cwd() == original
    assert rig._temp_dir is None


def test_partial_role_setup_retains_providers_after_workspace_cleanup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from henchman.agents import pool
    from henchman.agents.presets import get_default_team

    original = Path.cwd()
    default, child = MockProvider(), MockProvider()
    close = AsyncMock()
    monkeypatch.setattr(child, "_client", SimpleNamespace(close=close), raising=False)
    settings = Settings()
    presets = get_default_team()
    settings.agents.agents["planner"] = presets["planner"].model_copy(update={"provider": "ollama"})
    settings.agents.agents["explorer"] = presets["explorer"].model_copy(update={"provider": "invalid"})
    created: list[str] = []

    def factory(_settings: Any, *, provider_name: str, **_kwargs: Any) -> MockProvider:
        created.append(provider_name)
        if provider_name == "invalid":
            raise ValueError("Second provider construction failed")
        return child

    monkeypatch.setattr(pool, "create_configured_provider", factory)
    rig = EvalTestRig(provider=default, profile="team", settings=settings)
    with pytest.raises(ValueError, match="Second provider"):
        rig.setup("partial-provider-setup")
    assert created == ["ollama", "invalid"]
    assert rig.providers == [default, child]
    assert Path.cwd() == original and rig._temp_dir is None
    with pytest.raises(RuntimeError, match="set up"):
        _ = rig.profile_metadata
    rig.providers.clear()
    assert rig.providers == [default, child]
    rig.cleanup()
    assert rig.providers == [default, child]
    close.assert_not_called()


def test_late_cached_provider_is_retained_after_cleanup(
    make_rig: Any, monkeypatch: pytest.MonkeyPatch,
) -> None:
    from henchman.agents import pool
    from henchman.agents.config import AgentConfig as RoleConfig

    rig = make_rig()
    initial = rig.providers
    late = MockProvider()
    close = AsyncMock()
    monkeypatch.setattr(late, "_client", SimpleNamespace(close=close), raising=False)
    monkeypatch.setattr(pool, "create_configured_provider", lambda *_args, **_kwargs: late)
    rig.orchestrator.pool.configs["late"] = RoleConfig(
        name="Late", role="late", description="Lazily created", provider="ollama",
        enabled=False,
    )
    assert rig.orchestrator.pool.get_agent("late").provider is late
    rig.cleanup()
    assert rig.providers == [*initial, late]
    close.assert_not_called()


def test_overlapping_call_ids_fail_closed_without_misattributing_results() -> None:
    from evals.models import ToolLog
    from evals.team_runtime import _TeamObservations

    logs: list[ToolLog] = []
    observations = _TeamObservations([], logs)
    for name in ("read_file", "write_file"):
        observations.record(AgentEvent(
            EventType.TOOL_CALL_REQUEST, ToolCall("duplicate", name, {}),
            source_agent="engineer",
        ))
    for name, success in (("read_file", True), ("write_file", False)):
        observations.record(AgentEvent(EventType.TOOL_CALL_RESULT, {
            "tool_call_id": "duplicate", "tool_name": name,
            "result": name, "success": success,
        }, source_agent="engineer"))
    assert [log.tool_name for log in logs] == ["read_file", "write_file"]
    assert all(not log.success and log.result_index is None for log in logs)
    assert all("ambiguous" in log.result.lower() for log in logs)
    assert any("duplicate" in diagnostic for diagnostic in observations.diagnostics)


async def test_malformed_correlations_fail_even_with_reported_root_success(
    make_rig: Any, monkeypatch: pytest.MonkeyPatch,
) -> None:
    from evals import team_runtime

    async def malformed(_orchestrator: Any, _prompt: str, render: Any) -> bool:
        for name in ("read_file", "write_file"):
            render(AgentEvent(
                EventType.TOOL_CALL_REQUEST, ToolCall("duplicate", name, {}),
                source_agent="engineer",
            ))
        return True

    monkeypatch.setattr(team_runtime, "run_orchestrator_json", malformed)
    rig = make_rig()
    result = await rig.run("Malformed events")
    assert not result.success
    assert result.error and "ambiguous" in result.error.lower()
    assert result.diagnostics


@pytest.mark.parametrize("profile", ["basic", "engineer", "team"])
async def test_event_observer_runs_after_retention_in_exact_result_order(
    make_rig: Any, profile: str,
) -> None:
    provider = MockProvider([
        [ToolCall("read", "read_file", {"path": "source.txt"})], "Finished",
    ])
    rig = make_rig(profile=profile, provider=provider)
    rig.create_file("source.txt", "original")
    observed: list[AgentEvent] = []

    def observe(event: AgentEvent) -> None:
        assert rig._events[-1] is event
        assert len(rig._events) == len(observed) + 1
        if profile == "team" and event.type == EventType.TOOL_CALL_RESULT:
            log = rig.get_tool_calls("read_file")[0]
            assert log.result_index == len(rig._events) - 1
            assert log.success
        observed.append(event)

    result = await rig.run("Read source.txt", observe_event=observe)
    assert result.success
    assert observed == result.events
    assert any(event.type == EventType.TOOL_CALL_RESULT for event in observed)


class ProgressThenWaitProvider(HeldProvider):
    async def chat_completion_stream(
        self, messages: list[Message], tools: list[ToolDeclaration] | None = None,
        temperature: float | None = None, max_tokens: int | None = None,
        **kwargs: Any,
    ) -> AsyncGenerator[StreamChunk, None]:
        try:
            yield StreamChunk(content="Observed progress")
            self.waiting.set()
            await asyncio.Event().wait()
        finally:
            self.closed.set()


@pytest.mark.parametrize("profile", ["basic", "engineer", "team"])
@pytest.mark.parametrize("error_type", [RuntimeError, TimeoutError])
async def test_observer_error_propagates_retains_event_and_closes_stream(
    make_rig: Any, profile: str, error_type: type[Exception],
) -> None:
    provider = ProgressThenWaitProvider()
    rig = make_rig(profile=profile, provider=provider)
    assert rig._agent is not None
    old_limit = rig._agent.base_tool_iterations
    failure = error_type("Artifact observation failed")

    def observe(event: AgentEvent) -> None:
        if event.type == EventType.CONTENT:
            raise failure

    with pytest.raises(error_type, match="Artifact observation failed") as raised:
        await rig.run("Wait", max_iterations=1, observe_event=observe)
    assert raised.value is failure
    assert provider.closed.is_set()
    assert rig._agent.base_tool_iterations == old_limit
    assert rig._events[-1].type == EventType.CONTENT
    assert rig._events[-1].data == "Observed progress"
    with pytest.raises(AssertionError):
        rig.assert_successful_runs()


@pytest.mark.parametrize("profile", ["basic", "engineer", "team"])
async def test_event_observer_timeout_and_cancellation_cleanup(
    make_rig: Any, profile: str,
) -> None:
    timed = make_rig(profile=profile, provider=HeldProvider())
    events: list[AgentEvent] = []
    result = await timed.run("Wait", timeout=0.03, observe_event=events.append)
    assert not result.success
    assert events == result.events
    assert events[-2].type == EventType.ERROR
    assert events[-1].type == EventType.FINISHED

    provider = ProgressThenWaitProvider()
    rig = make_rig(profile=profile, provider=provider)
    assert rig._agent is not None
    old_limit = rig._agent.base_tool_iterations
    observed: list[AgentEvent] = []
    task = asyncio.create_task(rig.run(
        "Wait for cancellation", timeout=5, max_iterations=1,
        observe_event=observed.append,
    ))
    await asyncio.wait_for(provider.waiting.wait(), timeout=3)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert provider.closed.is_set()
    assert rig._agent.base_tool_iterations == old_limit
    assert observed == rig._events
    assert any(event.type == EventType.CONTENT for event in observed)
