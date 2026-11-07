"""Typed tool evidence survives runtime, wire projection, and retained history."""

from __future__ import annotations

import copy
import json
from io import StringIO
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from rich.console import Console

from henchman.core.agent import Agent
from henchman.providers.base import Message, ModelProvider, ToolCall
from henchman.tools.base import ToolResult


def typed_result(*, structured=None, present=True) -> ToolResult:
    return ToolResult(
        content="readable",
        content_blocks=(
            {"type": "text", "text": "readable"},
            {
                "type": "image",
                "mimeType": "image/png",
                "data": "aGVsbG8=",
                "annotations": {"audience": ["assistant"]},
            },
        ),
        structured_content=structured,
        structured_content_present=present,
        metadata={"source": "fixture", "details": {"retained": True}},
    )


def test_agent_records_detached_typed_result_with_explicit_null() -> None:
    agent = Agent(provider=MagicMock(spec=ModelProvider))
    result = typed_result()
    agent.submit_tool_result("call", result)
    message = agent.messages[-1]
    assert message.content == "readable"
    assert message.tool_result["structured_content_present"] is True
    assert "structured_content" in message.tool_result
    assert message.tool_result["structured_content"] is None
    result.content_blocks[0]["text"] = "changed after submission"
    result.metadata["details"]["retained"] = False
    assert message.tool_result["content_blocks"][0]["text"] == "readable"
    assert message.tool_result["metadata"]["details"]["retained"] is True


@pytest.mark.parametrize(
    "provider_name", ["openai_compat", "deepseek", "openrouter", "ollama", "anthropic"]
)
def test_provider_tool_projection_preserves_metadata_and_names_unsupported_media(
    provider_name: str,
) -> None:
    from henchman.providers.anthropic import AnthropicProvider
    from henchman.providers.deepseek import DeepSeekProvider
    from henchman.providers.ollama import OllamaProvider
    from henchman.providers.openai_compat import OpenAICompatibleProvider
    from henchman.providers.openrouter import OpenRouterProvider

    classes = {
        "openai_compat": OpenAICompatibleProvider,
        "deepseek": DeepSeekProvider,
        "openrouter": OpenRouterProvider,
        "ollama": OllamaProvider,
        "anthropic": AnthropicProvider,
    }
    agent = Agent(provider=MagicMock(spec=ModelProvider))
    agent.submit_tool_result("call", typed_result(structured={"items": [1, None]}))
    message = agent.messages[-1]
    # These production formatters do not require a transport or model request.
    provider = object.__new__(classes[provider_name])
    if provider_name == "anthropic":
        _, messages = provider._format_messages([message])
        content = messages[0]["content"][0]["content"]
    else:
        content = provider._format_message(message)["content"]
    assert "fixture" in content and "retained" in content
    assert "items" in content and "null" in content
    assert "image/png" in content and "unsupported" in content.lower()
    assert "aGVsbG8=" not in content
    assert message.tool_result["content_blocks"][1]["data"] == "aGVsbG8="


def test_legacy_string_messages_keep_their_existing_wire_content() -> None:
    from henchman.providers.anthropic import _format_tool_result
    from henchman.providers.openai_compat import _format_message

    message = Message(role="tool", content="legacy text", tool_call_id="call")
    assert _format_message(message)["content"] == "legacy text"
    assert _format_tool_result(message)["content"][0]["content"] == "legacy text"


async def test_native_mcp_headless_result_preserves_typed_json_and_redacts_only_evidence(
    tmp_path,
) -> None:
    from henchman.cli.app import _process_tool_calls
    from henchman.cli.json_output import JsonOutputRenderer
    from henchman.mcp.manager import McpManager
    from henchman.tools.registry import ToolRegistry
    from henchman.utils.evidence_redaction import EvidenceRedactor
    from tests.mcp.test_catalog_fidelity import Fixture, declaration, state

    secret = "typed-result-private-canary"
    fixture = Fixture(
        tmp_path,
        state(
            declaration("typed"),
            results={
                "typed": {
                    "content": [{"type": "text", "text": "visible"}],
                    "structuredContent": None,
                    "_meta": {"api_key": secret, "echo": secret},
                }
            },
        ),
    )
    manager = McpManager({"fixture": fixture.config})
    registry = ToolRegistry()

    async def approve(_request):
        return True

    registry.set_confirmation_handler(approve)
    try:
        await manager.connect_server("fixture")
        manager.bind_registry(registry)
        agent = Agent(provider=MagicMock(spec=ModelProvider), tool_registry=registry)
        events = []
        await _process_tool_calls(
            SimpleNamespace(agent=agent), [ToolCall("call", "mcp_fixture_typed", {})], events.append
        )
        payload = events[0].data["tool_result"]
        assert payload["structured_content_present"] and payload["structured_content"] is None
        assert agent.messages[-1].tool_result["metadata"]["echo"] == secret
        capture = StringIO()
        renderer = JsonOutputRenderer(Console(file=capture), redactor=EvidenceRedactor())
        renderer.render(events[0])
        rendered = json.loads(capture.getvalue())
        assert secret not in capture.getvalue()
        assert rendered["data"]["tool_result"]["metadata"]["echo"] == "[REDACTED]"
        assert rendered["data"]["tool_call_id"] == "call"
        assert payload["metadata"]["echo"] == secret
    finally:
        await manager.disconnect_all()


def test_typed_session_history_and_compaction_round_trip_preserve_presence(tmp_path) -> None:
    from henchman.core.session import SessionManager
    from henchman.core.session_context import SessionContextService
    from henchman.core.session_models import SessionMessage

    agent = Agent(provider=MagicMock(spec=ModelProvider))
    agent.submit_tool_result("call", typed_result(present=False))
    payload = copy.deepcopy(agent.messages[-1].tool_result)
    manager = SessionManager(data_dir=tmp_path / "sessions")
    session = manager.create_session(project_hash="typed")
    session.messages = [
        SessionMessage("user", "first"),
        SessionMessage("assistant", tool_calls=[{"id": "call", "name": "typed", "arguments": {}}]),
        SessionMessage("tool", "readable", tool_call_id="call", tool_result=payload),
        SessionMessage("assistant", "done"),
        SessionMessage("user", "second"),
        SessionMessage("assistant", "next"),
    ]
    service = SessionContextService(manager)
    service.compact_session(session, preserve_turns=1)
    manager.save(session)
    loaded = manager.load(session.id)
    recovered = service.restore_compacted_messages(loaded)
    assert recovered[2].tool_result == payload
    assert recovered[2].tool_result["structured_content_present"] is False
    assert "structured_content" not in recovered[2].tool_result


def test_active_compaction_marks_typed_projection_without_mutating_retained_original() -> None:
    from henchman.utils.compaction import _truncate_tool_message_content

    agent = Agent(provider=MagicMock(spec=ModelProvider))
    agent.submit_tool_result("call", typed_result(structured={"long": "x" * 5000}))
    message = agent.messages[-1]
    before = copy.deepcopy(message.tool_result)
    compacted = _truncate_tool_message_content(message, 1000)
    assert message.tool_result == before
    assert compacted.tool_result["projection_truncated"] is True
    assert "omitted" in compacted.content.lower()


def test_summary_and_token_estimates_include_structured_only_results() -> None:
    from henchman.utils.compaction import _format_messages_for_summary_content
    from henchman.utils.tokens import TokenCounter

    agent = Agent(provider=MagicMock(spec=ModelProvider))
    agent.submit_tool_result(
        "call",
        ToolResult(
            "", structured_content={"meaningful": "answer " * 80}, structured_content_present=True
        ),
    )
    message = agent.messages[-1]
    assert "meaningful" in _format_messages_for_summary_content([message])
    counter = TokenCounter()
    assert (
        counter.count_messages([message])
        > counter.count_messages([Message("tool", "", tool_call_id="call")]) + 50
    )


async def test_chat_tool_result_retains_typed_payload_and_displays_visible_media_summary() -> None:
    from henchman.chat.manager import ChatManager
    from henchman.config.schema import Settings
    from henchman.core.events import AgentEvent, EventType

    result = typed_result(structured={"answer": 42})
    agent = Agent(provider=MagicMock(spec=ModelProvider))
    agent.tool_registry = SimpleNamespace(execute=AsyncMock(return_value=result))
    bot = SimpleNamespace(send_message=AsyncMock(return_value=True))

    async def stream():
        yield AgentEvent(EventType.TOOL_CALL_REQUEST, ToolCall("call", "typed", {}))

    await ChatManager(Settings())._process_stream(agent, bot, "fixture-user", stream(), [], "")
    assert agent.messages[-1].tool_result["structured_content"] == {"answer": 42}
    displayed = "\n".join(call.args[1] for call in bot.send_message.await_args_list)
    assert "unsupported" in displayed and "image/png" in displayed
    assert "aGVsbG8=" not in displayed


@pytest.mark.parametrize("control", ["recovery", "budget"])
async def test_parallel_tool_controls_propagate_without_model_continuation(control) -> None:
    from henchman.cli.tool_executor import ToolExecutor
    from henchman.core.operation_recovery import OperationRecoveryError
    from henchman.core.run_budget import BudgetControlError
    from tests.cli.test_tool_executor_asyncio_gather import (
        TestParallelToolCallFailureHandling,
        _FakeAgent,
    )

    executor = TestParallelToolCallFailureHandling()._make_executor()
    agent = _FakeAgent(executor.tool_manager.registry)
    failure = (
        OperationRecoveryError("outcome_unknown")
        if control == "recovery"
        else BudgetControlError("fixture_stop")
    )
    agent.tool_registry.execute = AsyncMock(side_effect=failure)
    executor.process_agent_stream = AsyncMock()
    with pytest.raises(type(failure)):
        await ToolExecutor.execute_tool_calls(executor, [ToolCall("call", "echo", {})], agent)
    executor.process_agent_stream.assert_not_called()


@pytest.mark.parametrize("malformation", ["type", "marker", "presence", "unexpected_identity"])
def test_typed_session_payload_rejects_untrusted_structural_values_without_echo(
    malformation,
) -> None:
    from henchman.core.session_models import message_from_dict
    from henchman.tools.contracts import SchemaContractError
    from henchman.utils.tool_results import tool_result_payload

    canary = "malformed-private-canary"
    payload = tool_result_payload(typed_result())
    if malformation == "type":
        payload["content_blocks"][0]["type"] = canary
    elif malformation == "marker":
        payload = {"projection_truncated": True, "payload_sha256": canary}
    elif malformation == "presence":
        del payload["structured_content"]
    else:
        payload["payload_sha256"] = canary
    with pytest.raises(SchemaContractError) as error:
        message_from_dict({"role": "tool", "content": "", "tool_result": payload})
    assert canary not in str(error.value)


def test_chat_session_restore_detaches_typed_payload_and_retains_reasoning(tmp_path) -> None:
    from henchman.cli.commands.chat import _restore_agent_history_from_session
    from henchman.core.session import SessionManager
    from henchman.core.session_models import SessionMessage
    from henchman.utils.tool_results import tool_result_payload

    agent = Agent(provider=MagicMock(spec=ModelProvider))
    session = SessionManager(data_dir=tmp_path).create_session(project_hash="fixture")
    payload = tool_result_payload(typed_result())
    session.messages = [
        SessionMessage(
            "tool",
            "readable",
            tool_call_id="call",
            tool_result=payload,
            reasoning_details="reasoning",
        )
    ]
    _restore_agent_history_from_session(SimpleNamespace(agent=agent), session)
    assert agent.messages[-1].tool_result == payload
    assert agent.messages[-1].reasoning_details == "reasoning"
    agent.messages[-1].tool_result["metadata"]["source"] = "mutated"
    assert payload["metadata"]["source"] == "fixture"


@pytest.mark.parametrize("method", ["enforce_safety_limits", "_enforce_message_safety_limit"])
def test_intelligent_safety_limits_account_for_typed_only_content_without_losing_provenance(
    method,
) -> None:
    from henchman.utils.intelligent_context_formatter import (
        MessageSafetyEnforcer,
        TokenCounterWrapper,
    )
    from henchman.utils.tool_results import tool_result_payload

    payload = tool_result_payload(typed_result(structured={"long": "word " * 2000}))
    message = Message(
        "tool", "", tool_call_id="call", tool_result=payload, reasoning_details="retained"
    )
    enforcer = MessageSafetyEnforcer(0.5, 1000)
    if method == "enforce_safety_limits":
        truncated = enforcer.enforce_safety_limits([message])[0]
    else:
        truncated = enforcer._enforce_message_safety_limit(message)
    assert truncated is not message
    assert truncated.tool_result["projection_truncated"] is True
    assert truncated.reasoning_details == "retained"
    assert TokenCounterWrapper.count_messages_tokens([message]) > 1000
    assert message.tool_result == payload


async def test_legacy_executor_and_orchestrator_event_reach_redacted_session_with_typed_fields(
    tmp_path,
) -> None:
    from henchman.agents.orchestrator_tools import _report_tool_result
    from henchman.cli.session_manager import ReplSessionManager, _sync_messages_to_agent
    from henchman.cli.stream_event_handlers import StreamState, _handle_tool_call_result
    from henchman.cli.tool_executor import ToolExecutor
    from henchman.core.session import SessionManager
    from henchman.utils.evidence_redaction import EvidenceRedactor
    from tests.cli.test_tool_executor_asyncio_gather import _EchoTool, _FakeOutputHandler

    secret = "typed-persistence-private-canary"
    result = typed_result(structured={"echo": secret})
    result.metadata["api_key"] = secret

    class TypedTool(_EchoTool):
        async def execute(self, **params):
            return result

    manager = SessionManager(
        data_dir=tmp_path / "sessions", evidence_redactor=EvidenceRedactor(["text"])
    )
    sessions = ReplSessionManager(manager)
    sessions.session = manager.create_session(project_hash="typed")
    output = _FakeOutputHandler()
    output.session_manager = sessions
    agent = Agent(provider=MagicMock(spec=ModelProvider))
    agent.tool_registry.register(TypedTool())
    executor = ToolExecutor(output, SimpleNamespace(registry=agent.tool_registry), agent.provider)
    await executor._execute_and_record_tool_call(
        ToolCall("first", "echo", {}), agent, set(), announce_request=False
    )
    assert agent.messages[-1].tool_result["structured_content"]["echo"] == secret
    event = _report_tool_result(agent, ToolCall("second", "echo", {}), result, [], MagicMock())
    state = StreamState()
    _handle_tool_call_result(output, event, state)
    assert state.handled_tool_call_ids == {"second"}
    path = manager.save(sessions.session)
    assert secret not in path.read_text()
    loaded = manager.load(sessions.session.id)
    assert len(loaded.messages) == 2
    for message in loaded.messages:
        assert message.tool_result["content_blocks"][0]["type"] == "text"
        assert message.tool_result["structured_content"]["echo"] == "[REDACTED]"
        assert message.tool_result["metadata"]["api_key"] == "[REDACTED]"
    _sync_messages_to_agent(agent, loaded)
    assert agent.messages[-1].tool_result == loaded.messages[-1].tool_result
    assert event.data["tool_result"]["metadata"]["api_key"] == secret


def test_failed_typed_result_keeps_error_status_after_active_truncation() -> None:
    from henchman.providers.anthropic import _format_tool_result
    from henchman.utils.compaction import _truncate_tool_message_content
    from henchman.utils.tool_results import tool_result_payload

    result = typed_result(structured={"failure": "detail " * 2000})
    result.success = False
    result.error = "failure description"
    message = Message("tool", "", tool_call_id="call", tool_result=tool_result_payload(result))
    compacted = _truncate_tool_message_content(message, 1000)
    block = _format_tool_result(compacted)["content"][0]
    assert block["is_error"] is True
    assert "omitted" in block["content"]


def test_protected_zone_truncates_structured_only_content_without_mutating_history() -> None:
    from henchman.utils.compaction import _truncate_protected_zone_messages
    from henchman.utils.tool_results import tool_result_payload

    payload = tool_result_payload(typed_result(structured={"long": "word " * 3000}))
    message = Message("tool", "", tool_call_id="call", tool_result=payload)
    compacted = _truncate_protected_zone_messages([message], 500)
    assert compacted[0].tool_result["projection_truncated"] is True
    assert message.tool_result == payload


def test_session_exports_and_merge_preserve_typed_results(tmp_path) -> None:
    from henchman.core.session import SessionManager
    from henchman.core.session_export import export_as_markdown
    from henchman.core.session_merge import _merge_smart
    from henchman.core.session_models import SessionMessage
    from henchman.core.session_vcr import SessionVcrService
    from henchman.utils.tool_results import tool_result_payload

    manager = SessionManager(data_dir=tmp_path)
    first = manager.create_session(project_hash="fixture")
    second = manager.create_session(project_hash="fixture")
    payload = tool_result_payload(typed_result(structured={"answer": 1}))
    first.messages = [SessionMessage("tool", "", tool_call_id="call", tool_result=payload)]
    second.messages = [
        SessionMessage(
            "tool",
            "",
            tool_call_id="call",
            tool_result=tool_result_payload(typed_result(structured={"answer": 2})),
        )
    ]
    assert len(_merge_smart([first, second])) == 2
    markdown = export_as_markdown(first)
    assert "answer" in markdown and "unsupported" in markdown
    assert "aGVsbG8=" not in markdown
    playback = SessionVcrService().build_playback(first)
    assert playback["events"][0]["tool_result"] == payload


@pytest.mark.parametrize("structured", [None, [1, None], 42, False])
def test_canonical_projection_preserves_json_values_without_claiming_native_mcp_scalar_support(
    structured,
) -> None:
    from henchman.utils.tool_results import (
        tool_message_content,
        tool_result_from_payload,
        tool_result_payload,
    )

    result = typed_result(structured=structured)
    payload = tool_result_payload(result)
    restored = tool_result_from_payload(result.content, payload)
    assert restored.structured_content_present is True
    assert restored.structured_content == structured
    wire = json.loads(tool_message_content(result.content, payload))["tool_result"]
    assert wire["structured_content_present"] is True
    assert wire["structured_content"] == structured


def test_short_text_cannot_hide_large_typed_payload_omission() -> None:
    from henchman.utils.tool_results import (
        compact_tool_payload,
        tool_message_content,
        tool_result_payload,
    )

    payload = tool_result_payload(typed_result(structured={"long": "word " * 3000}))
    compacted = compact_tool_payload(payload)
    projected = tool_message_content("success", compacted)
    assert "omitted" in projected
    assert compacted["payload_sha256"] in projected
    assert "success" in projected
    assert "retained locally" not in projected and "session history" not in projected


def test_binary_projection_describes_the_supplied_redacted_evidence_without_retention_claims() -> (
    None
):
    from henchman.utils.evidence_redaction import EvidenceRedactor
    from henchman.utils.tool_results import (
        TOOL_RESULT_SCHEMA,
        tool_message_content,
        tool_result_payload,
    )

    payload = tool_result_payload(typed_result())
    projected = EvidenceRedactor(["aGVsbG8="]).redact(payload, schema=TOOL_RESULT_SCHEMA)
    wire = json.loads(tool_message_content("", projected))["tool_result"]
    projection = wire["content_blocks"][1]["projection"]
    assert projection["provided_data_characters"] == len("[REDACTED]")
    assert "retained" not in projection["reason"]
    assert "not sent as binary" in projection["reason"]


def test_typed_messages_and_retained_history_match_published_runtime_contracts(tmp_path) -> None:
    from dataclasses import asdict

    from henchman.core.session import SessionManager
    from henchman.core.session_models import SessionMessage, TurnSummaryRecord
    from henchman.testing.contract import ContractSuite
    from henchman.utils.tool_results import tool_result_payload
    from tests.contracts.helpers import assert_contract_matches

    payload = tool_result_payload(typed_result())
    message = Message("tool", "text", tool_call_id="call", tool_result=payload)
    saved = SessionMessage("tool", "text", tool_call_id="call", tool_result=payload, reasoning_details="details")
    summary = TurnSummaryRecord(1, "compacted", kind="compaction", source_turns=[1], retained_messages=[saved])
    session = SessionManager(data_dir=tmp_path).create_session(project_hash="fixture")
    session.messages = [saved]
    session.turn_summaries = [summary]
    suite = ContractSuite()
    for name, value in (("message", asdict(message)), ("session_message", saved.to_dict()),
                        ("turn_summary_record", summary.to_dict()), ("session", session.to_dict())):
        assert_contract_matches(payload=value, schema_name=f"runtime/{name}", contract_suite=suite)
