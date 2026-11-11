"""Opaque provider state survives storage or explicitly stops before reuse."""

from copy import deepcopy
from dataclasses import asdict
from types import SimpleNamespace

import pytest

from henchman.agents.pool import AgentPool
from henchman.cli.provider_switch import switch_runtime_provider
from henchman.cli.session_manager import _sync_messages_to_agent
from henchman.config.schema import Settings
from henchman.core.agent import Agent
from henchman.core.session import Session, SessionMessage, session_from_dict
from henchman.core.session_context import _message_to_provider_message
from henchman.core.session_evidence import redact_session_payload, redact_template_payload
from henchman.providers.anthropic import AnthropicProvider
from henchman.providers.base import ContextTooLargeError, Message, ToolCall
from henchman.providers.continuation import (
    ContinuationEnvelope,
    ProviderContinuationError,
    validate_continuations,
)
from henchman.utils.compaction import _enforce_message_content_safety
from henchman.utils.evidence_redaction import EvidenceRedactor


def message(provider, content="Checking."):
    blocks = [{"type": "thinking", "thinking": "Inspect", "signature": "signature-canary"},
              {"type": "text", "text": content},
              {"type": "tool_use", "id": "call", "name": "inspect", "input": {}}]
    return Message("assistant", content, tool_calls=[ToolCall("call", "inspect", {})], reasoning_content="Inspect",
                   continuation=ContinuationEnvelope.create(provider, blocks).to_dict())


def test_session_roundtrip_and_both_agent_restore_paths_preserve_envelope():
    provider = AnthropicProvider(api_key="offline-test", model="model-a")
    original = message(provider)
    session = Session("session", "project", "now", "now", messages=[SessionMessage(**asdict(original))])
    saved = session.to_dict()
    restored = session_from_dict(saved)
    assert restored.messages[0].continuation == original.continuation
    converted = _message_to_provider_message(restored.messages[0])
    assert converted.continuation == original.continuation
    agent = Agent(provider)
    _sync_messages_to_agent(agent, restored)
    assert agent.messages[-1].continuation == original.continuation
    restored.messages[0].continuation["status"] = "changed"
    assert agent.messages[-1].continuation == original.continuation


@pytest.mark.parametrize("location", ["messages", "summary", "specialist", "template"])
def test_redaction_invalidates_opaque_state_at_every_session_evidence_location(location):
    provider = AnthropicProvider(api_key="offline-test", model="model-a")
    original = asdict(message(provider))
    payload = {"messages": [original]} if location in {"messages", "template"} else (
        {"turn_summaries": [{"retained_messages": [original]}]} if location == "summary" else
        {"operations": {"conversations": [{"id": "turn:agent", "messages": [original]}]}})
    policy = EvidenceRedactor()
    policy.register_secret("signature-canary")
    projected = (redact_template_payload({"session_data": payload}, policy) if location == "template"
                 else redact_session_payload(payload, policy))
    assert "signature-canary" not in str(projected)
    assert "redacted_continuation" in str(projected)
    assert original["continuation"]["status"] == "complete"


def test_signed_message_cannot_be_partially_truncated_to_fit_context():
    provider = AnthropicProvider(api_key="offline-test", model="model-a")
    original = message(provider, "Long output. " * 1000)
    before = deepcopy(original)
    with pytest.raises(ContextTooLargeError):
        _enforce_message_content_safety(original, 10)
    assert original == before


def test_pool_rejects_incompatible_cached_specialist_before_mutating_any_agent():
    original = AnthropicProvider(api_key="offline-test", model="model-a")
    replacement = AnthropicProvider(api_key="offline-test", model="model-b")
    first, second = Agent(original), Agent(original)
    second.messages = [message(original)]
    pool = object.__new__(AgentPool)
    pool.default_provider = original
    pool._agents = {"first": first, "second": second}
    pool.configs = {name: SimpleNamespace(provider=None, model=None) for name in pool._agents}
    with pytest.raises(ProviderContinuationError):
        pool.set_default_provider(replacement)
    assert pool.default_provider is original
    assert first.provider is original and second.provider is original


def test_runtime_switch_preflights_standalone_active_agent_before_mutating_pool():
    original = AnthropicProvider(api_key="offline-test", model="model-a")
    replacement = AnthropicProvider(api_key="offline-test", model="model-b")
    cached, active = Agent(original), Agent(original)
    active.messages = [message(original)]
    pool = object.__new__(AgentPool)
    pool.default_provider = original
    pool._agents = {"first": cached}
    pool.configs = {"first": SimpleNamespace(provider=None, model=None)}
    runtime = SimpleNamespace(provider=original, agent=active, settings=Settings(),
                             orchestrator=SimpleNamespace(pool=pool, default_provider=original))
    with pytest.raises(ProviderContinuationError):
        switch_runtime_provider(runtime, replacement)
    assert pool.default_provider is original and cached.provider is original
    assert runtime.provider is original and active.provider is original


def test_modified_tool_arguments_cannot_reuse_unmodified_native_envelope():
    provider = AnthropicProvider(api_key="offline-test", model="model-a")
    modified = message(provider)
    modified.tool_calls[0].arguments["changed"] = True
    with pytest.raises(ProviderContinuationError, match="transcript_mismatch"):
        validate_continuations([modified], provider)


def test_atomic_session_save_and_compaction_retain_opaque_bytes_without_rendering(tmp_path):
    from henchman.core.session import SessionManager
    from henchman.core.session_context import SessionContextService
    from henchman.core.session_export import export_as_markdown
    from henchman.utils.compaction import MessageSummarizer

    provider = AnthropicProvider(api_key="offline-test", model="model-a")
    signed = message(provider)
    manager = SessionManager(tmp_path / "sessions")
    session = manager.create_session("project")
    session.messages = [SessionMessage("user", "Inspect"), SessionMessage(**asdict(signed)),
                        SessionMessage("tool", "Observed", tool_call_id="call"),
                        SessionMessage("user", "Another task"), SessionMessage("assistant", "Done")]
    changed = SessionContextService(manager).compact_session(session, preserve_turns=1)
    assert changed.changed
    manager.save(session)
    restored = SessionManager(tmp_path / "sessions").load(session.id)
    retained = next(item for item in restored.turn_summaries[-1].retained_messages if item.continuation is not None)
    assert retained.continuation == signed.continuation
    assert "signature-canary" not in export_as_markdown(restored)
    assert "signature-canary" not in MessageSummarizer()._format_messages_for_summary([signed])
    assert "signature-canary" not in repr(signed)


def test_hard_request_compaction_preserves_current_signed_exchange_and_full_evidence():
    from henchman.core.request_budget import prepare_request
    from henchman.utils.tokens import TokenCounter

    provider = AnthropicProvider(api_key="offline-test", model="model-a", max_tokens=16)
    signed = message(provider)
    messages = [Message("user", "Old " * 4000), Message("assistant", "Old answer"),
                Message("user", "Inspect"), signed, Message("tool", "Observed", tool_call_id="call")]
    before = deepcopy(messages)
    prepared = prepare_request(provider, messages, [], context_window=1000, conversation_limit=500,
                               protect_from_index=2)
    assert prepared.compacted
    assert prepared.messages == messages[2:]
    assert prepared.messages[1].continuation == signed.continuation
    assert messages == before
    assert TokenCounter.count_messages([signed]) > TokenCounter.count_messages([Message("assistant", signed.content)])
    with pytest.raises(ContextTooLargeError):
        prepare_request(provider, messages[2:], [], context_window=40, conversation_limit=40, protect_from_index=0)
    assert messages == before


def test_compaction_cannot_remove_unavailable_state_before_predispatch_validation():
    from dataclasses import replace

    from henchman.core.request_budget import prepare_request

    provider = AnthropicProvider(api_key="offline-test", model="model-a", max_tokens=16)
    signed = message(provider)
    signed.continuation = replace(ContinuationEnvelope.from_dict(signed.continuation), payload_json=None,
                                  status="unavailable", reason="redacted_continuation").to_dict()
    messages = [Message("user", "Old task"), signed, Message("tool", "Observed", tool_call_id="call"),
                Message("user", "New task")]
    with pytest.raises(ProviderContinuationError, match="unavailable"):
        prepare_request(provider, messages, [], context_window=1000, conversation_limit=10, protect_from_index=3)
    assert len(messages) == 4


def test_session_merge_does_not_deduplicate_different_provider_continuations():
    from henchman.core.session_merge import _merge_smart

    first = AnthropicProvider(api_key="offline-test", model="model-a")
    second = AnthropicProvider(api_key="offline-test", model="model-b")
    sessions = [Session(str(index), "project", "now", "now", messages=[SessionMessage(**asdict(message(provider)))])
                for index, provider in enumerate((first, second))]
    merged = _merge_smart(sessions)
    assert len(merged) == 2
    assert merged[0].continuation["model"] == "model-a"
    assert merged[1].continuation["model"] == "model-b"
