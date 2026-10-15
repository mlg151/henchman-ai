"""Offline contracts for the live evaluation harness and real coding tools."""

import asyncio

import pytest
from evals import helpers
from evals.helpers import EvalTestRig, MockProvider, get_eval_provider

from henchman.core.agent_config import AgentConfig
from henchman.core.events import EventType
from henchman.providers.base import FinishReason, StreamChunk, ToolCall


@pytest.fixture(autouse=True)
def clean_eval_environment(monkeypatch):
    for name in (
        "EVAL_PROVIDER", "EVAL_MODEL", "EVAL_BASE_URL", "EVAL_TIMEOUT", "EVAL_PROFILE",
        "DEEPSEEK_API_KEY", "ANTHROPIC_API_KEY", "OPENROUTER_API_KEY", "HENCHMAN_API_KEY",
    ):
        monkeypatch.delenv(name, raising=False)


def test_explicit_missing_provider_key_never_uses_another_paid_provider(monkeypatch):
    monkeypatch.setenv("EVAL_PROVIDER", "deepseek")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "unrelated-key")
    with pytest.raises(RuntimeError, match="deepseek"):
        get_eval_provider()


def test_unknown_eval_provider_never_falls_back(monkeypatch):
    monkeypatch.setenv("EVAL_PROVIDER", "misspelled")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "unrelated-key")
    with pytest.raises(RuntimeError, match="misspelled"):
        get_eval_provider()


def test_generic_local_eval_endpoint_uses_explicit_configuration(monkeypatch):
    monkeypatch.setenv("EVAL_PROVIDER", "openai_compat")
    monkeypatch.setenv("EVAL_MODEL", "local/coder")
    monkeypatch.setenv("EVAL_BASE_URL", "http://127.0.0.1:8080/v1")
    provider = get_eval_provider()
    assert provider.name == "openai-compatible"
    assert provider.default_model == "local/coder"
    assert provider.base_url == "http://127.0.0.1:8080/v1"


def test_explicit_openrouter_selected_without_other_keys(monkeypatch):
    monkeypatch.setenv("EVAL_PROVIDER", "openrouter")
    monkeypatch.setenv("EVAL_MODEL", "chosen/model")
    monkeypatch.setenv("OPENROUTER_API_KEY", "fake-test-key")
    provider = get_eval_provider()
    assert provider.name == "openrouter"
    assert provider.default_model == "chosen/model"


class DelayedProvider(MockProvider):
    """A bounded local stream that reveals cancellation cleanup."""

    closed = False

    async def chat_completion_stream(self, messages, tools=None, **kwargs):
        try:
            await asyncio.sleep(0.2)
            yield StreamChunk(content="Late", finish_reason=FinishReason.STOP)
        finally:
            self.closed = True


class ErrorProvider(MockProvider):
    async def chat_completion_stream(self, messages, tools=None, **kwargs):
        yield StreamChunk(content="Partial")
        raise RuntimeError("provider failed")


class TruncatedProvider(MockProvider):
    async def chat_completion_stream(self, messages, tools=None, **kwargs):
        yield StreamChunk(content="Incomplete", finish_reason=FinishReason.LENGTH)


@pytest.fixture
def make_rig():
    rigs = []

    def make(provider):
        rig = EvalTestRig(provider=provider)
        rig.setup("offline-harness")
        rigs.append(rig)
        return rig

    yield make
    for rig in reversed(rigs):
        rig.cleanup()


async def test_eval_timeout_is_enforced_and_stream_closed(make_rig):
    provider = DelayedProvider()
    result = await make_rig(provider).run("Wait", timeout=0.01)
    assert not result.success
    assert "timed out" in result.error.lower()
    assert provider.closed


async def test_eval_timeout_environment_default_is_honored(make_rig, monkeypatch):
    monkeypatch.setenv("EVAL_TIMEOUT", "0.01")
    result = await make_rig(DelayedProvider()).run("Wait")
    assert not result.success
    assert "timed out" in result.error.lower()


@pytest.mark.parametrize("provider", [ErrorProvider, TruncatedProvider])
async def test_failed_terminal_is_not_success(make_rig, provider):
    result = await make_rig(provider()).run("Finish the task")
    assert not result.success
    assert result.error
    assert any(event.type == EventType.ERROR for event in result.events)


async def test_iteration_exhaustion_does_not_execute_queued_tools(make_rig):
    call = ToolCall(id="write", name="write_file", arguments={"path": "unapproved.txt", "content": "x"})
    rig = make_rig(MockProvider([[call]]))
    result = await rig.run("Write", max_iterations=0)
    assert not result.success
    assert "iteration limit" in result.error.lower()
    assert not rig.file_exists("unapproved.txt")
    cancelled = [event for event in result.events if event.type == EventType.TOOL_CALL_RESULT]
    assert len(cancelled) == 1 and cancelled[0].data["tool_call_id"] == "write"
    assert cancelled[0].data["success"] is False


async def test_success_executes_real_file_tool_with_correlated_evidence(make_rig):
    provider = MockProvider()
    provider.set_tool_response("write_file", {"path": "answer.py", "content": "answer = 42\n"}, "Saved.")
    rig = make_rig(provider)
    result = await rig.run("Create answer.py")
    assert result.success, result.error
    assert rig.read_file("answer.py") == "answer = 42\n"
    assert result.final_response == "Saved."
    assert result.tool_logs[0].success
    assert result.tool_logs[0].arguments == {"path": "answer.py", "content": "answer = 42\n"}
    tool_events = [event for event in result.events if event.type == EventType.TOOL_CALL_RESULT]
    assert len(tool_events) == 1 and tool_events[0].data["tool_call_id"] == "call_0"


async def test_each_eval_run_has_its_own_event_evidence(make_rig):
    rig = make_rig(MockProvider(["First", "Second"]))
    first = await rig.run("One")
    second = await rig.run("Two")
    assert first.final_response == "First"
    assert second.final_response == "Second"
    assert [event.data for event in second.events if event.type == EventType.CONTENT] == ["Second"]


async def test_explicit_agent_config_is_copied_and_limits_restored():
    config = AgentConfig(max_tokens=3072, base_tool_iterations=7, system_prompt="Custom context")
    rig = EvalTestRig(provider=MockProvider(["Done"]), config=config)
    try:
        rig.setup("configured-agent")
        assert rig._agent.max_tokens == 3072
        assert rig._agent.history[0].content == "Custom context"
        result = await rig.run("Finish", max_iterations=1)
        assert result.success
        assert rig._agent.base_tool_iterations == 7
        assert config.base_tool_iterations == 7
        assert rig._agent._config is not config
    finally:
        rig.cleanup()


async def test_eval_cancellation_propagates_and_closes_stream(make_rig):
    provider = DelayedProvider()
    rig = make_rig(provider)
    task = asyncio.create_task(rig.run("Wait", timeout=5))
    await asyncio.sleep(0.01)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert provider.closed


@pytest.mark.parametrize("options", [{"timeout": 0}, {"timeout": float("nan")}, {"max_iterations": -1}])
async def test_eval_rejects_invalid_limits(make_rig, options):
    provider = MockProvider(["Must not run"])
    with pytest.raises(ValueError):
        await make_rig(provider).run("Check", **options)
    assert provider.calls == []


@pytest.mark.parametrize("provider,options", [
    (ErrorProvider, {}),
    (TruncatedProvider, {}),
    (DelayedProvider, {"timeout": 0.01}),
    (lambda: MockProvider([[ToolCall(id="queued", name="read_file", arguments={"path": "x"})]]),
     {"max_iterations": 0}),
])
async def test_decorated_eval_cannot_ignore_failed_runtime(monkeypatch, provider, options):
    monkeypatch.setattr(helpers, "get_eval_provider", provider)
    directories = []

    @helpers.eval_test("ALWAYS_PASSES")
    async def scenario(rig):
        directories.append(rig.test_dir)
        await rig.run("Perform the task", **options)

    with pytest.raises(AssertionError, match="[Tt]urn 1"):
        await scenario()
    assert directories and not directories[0].exists()


async def test_decorated_eval_requires_an_actual_agent_turn(monkeypatch):
    monkeypatch.setattr(helpers, "get_eval_provider", MockProvider)

    @helpers.eval_test("ALWAYS_PASSES")
    async def scenario(rig):
        rig.create_file("fake-result.py", "answer = 42")

    with pytest.raises(AssertionError, match="did not run"):
        await scenario()


async def test_later_success_and_mutated_result_cannot_erase_failed_turn(monkeypatch):
    provider = MockProvider([
        [ToolCall(id="queued", name="read_file", arguments={"path": "missing"})],
        "Finished the later turn",
    ])
    monkeypatch.setattr(helpers, "get_eval_provider", lambda: provider)

    @helpers.eval_test("ALWAYS_PASSES")
    async def scenario(rig):
        first = await rig.run("First", max_iterations=0)
        assert not first.success
        first.success, first.error = True, None
        assert (await rig.run("Second")).success

    with pytest.raises(AssertionError, match="[Tt]urn 1"):
        await scenario()


async def test_decorated_successful_turns_preserve_scenario_assertions_and_cleanup(monkeypatch):
    monkeypatch.setattr(helpers, "get_eval_provider", lambda: MockProvider(["One", "Two"]))
    directories = []

    @helpers.eval_test("ALWAYS_PASSES")
    async def scenario(rig):
        directories.append(rig.test_dir)
        assert (await rig.run("First")).final_response == "One"
        assert (await rig.run("Second")).final_response == "Two"

    await scenario()
    assert not directories[0].exists()


async def test_caught_cancellation_cannot_be_hidden_by_later_success(monkeypatch):
    entered = asyncio.Event()

    class HeldProvider(MockProvider):
        async def chat_completion_stream(self, messages, tools=None, **kwargs):
            entered.set()
            await asyncio.Event().wait()
            yield StreamChunk(content="Unreachable", finish_reason=FinishReason.STOP)

    monkeypatch.setattr(helpers, "get_eval_provider", HeldProvider)

    @helpers.eval_test("ALWAYS_PASSES")
    async def scenario(rig):
        running = asyncio.create_task(rig.run("First"))
        await asyncio.wait_for(entered.wait(), timeout=5)
        running.cancel()
        with pytest.raises(asyncio.CancelledError):
            await running
        rig._agent.set_provider(MockProvider(["Finished later"]))
        assert (await rig.run("Second")).success

    with pytest.raises(AssertionError, match="Turn 1: Evaluation did not complete"):
        await scenario()


async def test_python_verification_uses_current_interpreter_and_workspace(tmp_path, monkeypatch):
    monkeypatch.setenv("PATH", str(tmp_path))
    (tmp_path / "answer.py").write_text("value = 42\n")
    await helpers.verify_python(tmp_path, "from answer import value; assert value == 42")


async def test_python_verification_cannot_disable_assertions_via_environment(tmp_path, monkeypatch):
    monkeypatch.setenv("PYTHONOPTIMIZE", "2")
    with pytest.raises(AssertionError, match="oracle rejected"):
        await helpers.verify_python(tmp_path, "assert False, 'oracle rejected'")


async def test_python_verification_bounds_failure_diagnostics(tmp_path):
    with pytest.raises(AssertionError) as error:
        await helpers.verify_python(
            tmp_path, "import sys; print('x'*100000); print('é'*100000, file=sys.stderr); sys.exit(7)",
        )
    assert "exit 7" in str(error.value)
    assert "truncated" in str(error.value)
    assert len(str(error.value)) < 18000


async def test_python_verification_timeout_propagates(tmp_path):
    with pytest.raises(TimeoutError):
        await helpers.verify_python(tmp_path, "import time; time.sleep(60)", timeout=0.05)


@pytest.mark.parametrize("code", ["import sys; sys.exit(0)", "import os; os._exit(0)"])
async def test_python_verification_rejects_early_success_exit(tmp_path, code):
    with pytest.raises(AssertionError, match="without completing"):
        await helpers.verify_python(tmp_path, code)
