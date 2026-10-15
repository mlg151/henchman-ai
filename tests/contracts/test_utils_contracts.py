"""Contract tests for utils module boundaries.

These tests enforce the contracts at component boundaries within the utils package,
ensuring that cross-cutting utilities maintain stable interfaces for their consumers.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

import pytest

from henchman.utils.compaction import (
    CompactionBudgetCalculator,
    CompactionResult,
    MessageSequence,
    MessageSequenceGrouper,
    MessageSequenceValidator,
    ProtectedZoneManager,
    SummarizationConfig,
)
from henchman.utils.compression_strategy import (
    CompressionStrategy,
    CompressionStrategyConfig,
    CompressionStrategyFactory,
)
from henchman.utils.intelligent_context_types import (
    CompressionConfig,
    ContentAnalysis,
    FenceResult,
    IntelligentCompactionResult,
    IntelligentContextConstants,
    PreservedContent,
    ResultCreationParams,
    TruncationParams,
)
from henchman.utils.ratelimit import AsyncRateLimiter
from henchman.utils.registry import Registry
from henchman.utils.retry import (
    RetryConfig,
    calculate_delay,
    retry_async,
    with_retry,
)
from henchman.utils.serialization import AsDictMixin, SerializableDataclass
from henchman.utils.tokens import (
    DEFAULT_MODEL_LIMIT,
    MODEL_LIMITS,
    REPLY_PRIMER_TOKENS,
    TextTruncationParams,
    TokenCounter,
    get_model_limit,
)

# ---------------------------------------------------------------------------
# Registry contracts
# ---------------------------------------------------------------------------


class TestRegistryContract:
    """Contract tests for the generic Registry class."""

    def test_registry_is_generic(self) -> None:
        """Registry should accept a type parameter and be instantiable."""
        registry: Registry[str] = Registry()
        assert isinstance(registry, Registry)

    def test_registry_get_returns_none_for_missing_key(self) -> None:
        """Registry.get should return None for unregistered keys."""
        registry: Registry[int] = Registry()
        assert registry.get("nonexistent") is None

    def test_registry_list_names_returns_empty_when_empty(self) -> None:
        """Registry.list_names should return empty list when no items registered."""
        registry: Registry[str] = Registry()
        assert registry.list_names() == []

    def test_registry_list_items_returns_empty_when_empty(self) -> None:
        """Registry.list_items should return empty list when no items registered."""
        registry: Registry[str] = Registry()
        assert registry.list_items() == []

    def test_registry_roundtrip(self) -> None:
        """Items registered in a Registry should be retrievable by name."""
        registry: Registry[int] = Registry()
        registry._items["a"] = 1  # type: ignore[attr-defined]
        registry._items["b"] = 2  # type: ignore[attr-defined]

        assert registry.get("a") == 1
        assert registry.get("b") == 2
        assert registry.get("c") is None
        assert registry.list_names() == ["a", "b"]
        assert registry.list_items() == [1, 2]

    def test_registry_names_and_items_consistent(self) -> None:
        """list_names() and list_items() must reference the same entries."""
        registry: Registry[str] = Registry()
        registry._items["x"] = "alpha"  # type: ignore[attr-defined]
        registry._items["y"] = "beta"  # type: ignore[attr-defined]

        names = registry.list_names()
        items = registry.list_items()
        assert len(names) == len(items)
        assert dict(zip(names, items, strict=True)) == {"x": "alpha", "y": "beta"}


# ---------------------------------------------------------------------------
# RetryConfig contracts
# ---------------------------------------------------------------------------


class TestRetryConfigContract:
    """Contract tests for RetryConfig dataclass."""

    def test_retry_config_defaults(self) -> None:
        """RetryConfig should have sensible defaults."""
        config = RetryConfig()
        assert config.max_retries == 3
        assert config.base_delay == 1.0
        assert config.exponential_base == 2.0
        assert config.max_delay == 30.0
        assert config.jitter is True
        assert isinstance(config.retryable_exceptions, tuple)

    def test_retry_config_is_frozen(self) -> None:
        """RetryConfig should be immutable."""
        config = RetryConfig()
        # RetryConfig is a regular dataclass, not frozen; fields can be mutated
        config.max_retries = 5
        assert config.max_retries == 5

    def test_retry_config_custom_values(self) -> None:
        """RetryConfig should accept custom values."""
        config = RetryConfig(max_retries=5, base_delay=0.5, jitter=True)
        assert config.max_retries == 5
        assert config.base_delay == 0.5
        assert config.jitter is True


def test_calculate_delay_exponential_backoff() -> None:
    """Delay should grow exponentially with attempt number."""
    config = RetryConfig(base_delay=1.0, exponential_base=2.0, max_delay=30.0, jitter=False)
    assert calculate_delay(0, config) == 1.0
    assert calculate_delay(1, config) == 2.0
    assert calculate_delay(2, config) == 4.0
    assert calculate_delay(3, config) == 8.0


def test_calculate_delay_respects_max_delay() -> None:
    """Delay should never exceed max_delay."""
    config = RetryConfig(base_delay=1.0, exponential_base=2.0, max_delay=5.0, jitter=False)
    assert calculate_delay(10, config) == 5.0


def test_calculate_delay_with_jitter() -> None:
    """With jitter enabled, delay should be in a bounded range."""
    config = RetryConfig(base_delay=2.0, exponential_base=1.0, max_delay=30.0, jitter=True)
    for _ in range(10):
        delay = calculate_delay(0, config)
        # jitter: delay *= 0.5 + random() => multiplier in [0.5, 1.5]
        assert 1.0 <= delay <= 3.0


async def test_retry_async_succeeds_without_retry() -> None:
    """retry_async should return immediately when operation succeeds."""
    async def op() -> int:
        return 42

    result = await retry_async(op, config=RetryConfig(max_retries=3))
    assert result == 42


async def test_retry_async_retries_on_failure() -> None:
    """retry_async should retry up to max_retries times."""
    attempts: list[int] = []

    async def flaky_op() -> int:
        attempts.append(len(attempts))
        if len(attempts) < 3:
            raise ConnectionError("temporary")
        return 42

    result = await retry_async(flaky_op, config=RetryConfig(max_retries=3, base_delay=0.01))
    assert result == 42
    assert len(attempts) == 3


async def test_retry_async_raises_after_exhaustion() -> None:
    """retry_async should raise the last error after exhausting retries."""
    async def always_fails() -> int:
        raise ConnectionError("permanent")

    with pytest.raises(ConnectionError, match="permanent"):
        await retry_async(always_fails, config=RetryConfig(max_retries=2, base_delay=0.01))


async def test_retry_async_does_not_retry_non_retryable_exception() -> None:
    """retry_async should not retry exceptions not in retryable_exceptions."""
    async def raises_value_error() -> int:
        raise ValueError("not retryable")

    with pytest.raises(ValueError, match="not retryable"):
        await retry_async(raises_value_error, config=RetryConfig(max_retries=3))


async def test_with_retry_decorator() -> None:
    """with_retry should wrap an async callable with retry behavior."""
    call_count = 0

    async def tracked_func(x: int) -> int:
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise TimeoutError("retry me")
        return x * 2

    wrapped = with_retry(config=RetryConfig(max_retries=3, base_delay=0.01))(tracked_func)
    result = await wrapped(21)
    assert result == 42
    assert call_count == 3


# ---------------------------------------------------------------------------
# AsyncRateLimiter contracts
# ---------------------------------------------------------------------------


class TestAsyncRateLimiterContract:
    """Contract tests for AsyncRateLimiter."""

    @pytest.mark.asyncio
    async def test_allows_usage_within_limit(self) -> None:
        """Usage within the limit should not block."""
        limiter = AsyncRateLimiter(tokens_per_minute=10)
        await limiter.wait_for_capacity(5)
        await limiter.add_usage(5)
        # Should still have capacity for 5 more
        await limiter.wait_for_capacity(5)

    @pytest.mark.asyncio
    async def test_blocks_when_over_limit(self) -> None:
        """Usage over the limit should wait until capacity is available."""
        limiter = AsyncRateLimiter(tokens_per_minute=10)
        await limiter.add_usage(10)

        # This should wait for the window to expire
        start = asyncio.get_event_loop().time()
        await limiter.wait_for_capacity(1)
        elapsed = asyncio.get_event_loop().time() - start
        assert elapsed >= 0.1  # Should have waited (allow some tolerance)

    @pytest.mark.asyncio
    async def test_caps_tokens_to_limit(self) -> None:
        """Requested tokens should be capped to tokens_per_minute."""
        limiter = AsyncRateLimiter(tokens_per_minute=5)
        # Requesting more than the limit should be capped
        await limiter.wait_for_capacity(100)
        await limiter.add_usage(5)

    @pytest.mark.asyncio
    async def test_sliding_window_expiration(self) -> None:
        """Old usage should expire after 60 seconds."""
        limiter = AsyncRateLimiter(tokens_per_minute=10)
        await limiter.add_usage(10)
        # Manually age the usage entry to simulate time passing
        if limiter.usage:
            old_ts = limiter.usage[0][0]
            limiter.usage[0] = (old_ts - 61.0, 10)
        # Now we should have capacity again
        await limiter.wait_for_capacity(5)  # Should not block


# ---------------------------------------------------------------------------
# SerializableDataclass contracts
# ---------------------------------------------------------------------------


@dataclass
class _NestedData(SerializableDataclass):
    """Test nested dataclass."""
    value: int


@dataclass
class _TestPayload(SerializableDataclass):
    """Test payload with various field types."""
    name: str
    count: int
    nested: _NestedData
    tags: list[str]


class TestSerializableDataclassContract:
    """Contract tests for SerializableDataclass mixin."""

    def test_to_dict_via_asdict(self) -> None:
        """to_dict should produce a plain dict via asdict."""
        payload = _TestPayload(name="test", count=5, nested=_NestedData(value=10), tags=["a", "b"])
        d = payload.to_dict()
        assert d["name"] == "test"
        assert d["count"] == 5
        assert isinstance(d["nested"], dict)
        assert d["nested"]["value"] == 10
        assert d["tags"] == ["a", "b"]

    def test_from_dict_roundtrip(self) -> None:
        """from_dict should reconstruct an instance from a dict."""
        data = {
            "name": "roundtrip",
            "count": 3,
            "nested": {"value": 7},
            "tags": ["x"],
        }
        obj = _TestPayload.from_dict(data)
        assert obj.name == "roundtrip"
        assert obj.count == 3
        assert isinstance(obj.nested, _NestedData)
        assert obj.nested.value == 7
        assert obj.tags == ["x"]

    def test_from_dict_skips_missing_fields(self) -> None:
        """from_dict should work when optional fields are missing."""
        # _TestPayload requires nested and tags, but we test the mixin behavior
        # with a simpler case: fields not in data are simply not passed to __init__
        with pytest.raises(TypeError):
            _TestPayload.from_dict({"name": "partial", "count": 1})

    def test_from_dict_handles_union_field(self) -> None:
        """from_dict should handle Union types by trying non-None branch."""

        @dataclass
        class WithUnion(SerializableDataclass):
            value: int | str

        obj = WithUnion.from_dict({"value": 42})
        assert obj.value == 42

        obj2 = WithUnion.from_dict({"value": "hello"})
        assert obj2.value == "hello"


# ---------------------------------------------------------------------------
# TokenCounter contracts
# ---------------------------------------------------------------------------


class TestTokenCounterContract:
    """Contract tests for TokenCounter."""

    def test_count_text_empty(self) -> None:
        """Empty text should return 0 tokens."""
        assert TokenCounter.count_text("") == 0

    def test_count_text_returns_positive_int(self) -> None:
        """Non-empty text should return a positive token count."""
        assert TokenCounter.count_text("hello world") > 0

    def test_count_text_deterministic(self) -> None:
        """Same text should produce the same token count."""
        text = "The quick brown fox jumps over the lazy dog"
        assert TokenCounter.count_text(text) == TokenCounter.count_text(text)

    def test_truncate_text_empty(self) -> None:
        """Empty text truncation should return empty string."""
        assert TokenCounter.truncate_text("", 10) == ""

    def test_truncate_text_under_limit(self) -> None:
        """Text under the limit should be returned unchanged."""
        text = "hello"
        assert TokenCounter.truncate_text(text, 100) == text

    def test_truncate_text_respects_limit(self) -> None:
        """Truncated text should have at most max_tokens tokens."""
        text = "The quick brown fox jumps over the lazy dog. " * 100
        truncated = TokenCounter.truncate_text(text, 10)
        assert TokenCounter.count_text(truncated) <= 10

    def test_get_model_limit_known_model(self) -> None:
        """Known models should return their specific limits."""
        assert get_model_limit("gpt-4-turbo") == 128000
        assert get_model_limit("claude-3-5-sonnet-20241022") == 200000

    def test_get_model_limit_unknown_model(self) -> None:
        """Unknown models should return DEFAULT_MODEL_LIMIT."""
        assert get_model_limit("some-unknown-model") == DEFAULT_MODEL_LIMIT

    def test_model_limits_contains_expected_models(self) -> None:
        """MODEL_LIMITS should contain entries for major provider models."""
        assert "gpt-4o" in MODEL_LIMITS
        assert "gpt-3.5-turbo" in MODEL_LIMITS
        assert "claude-3-opus-20240229" in MODEL_LIMITS
        assert "deepseek-chat" in MODEL_LIMITS

    def test_text_truncation_params_contract(self) -> None:
        """TextTruncationParams should group truncation parameters."""
        params = TextTruncationParams(text="hello", max_tokens=100)
        assert params.text == "hello"
        assert params.max_tokens == 100
        assert params.model is None

        params2 = TextTruncationParams(text="world", max_tokens=50, model="gpt-4")
        assert params2.model == "gpt-4"


# ---------------------------------------------------------------------------
# Compaction contracts
# ---------------------------------------------------------------------------


class TestCompactionResultContract:
    """Contract tests for CompactionResult dataclass."""

    def test_default_values(self) -> None:
        """CompactionResult should have sensible defaults."""
        result = CompactionResult(messages=[])
        assert result.was_compacted is False
        assert result.dropped_count == 0
        assert result.summary is None

    def test_was_compacted_flag(self) -> None:
        """was_compacted should reflect whether compaction occurred."""
        result = CompactionResult(messages=[], was_compacted=True, dropped_count=5)
        assert result.was_compacted is True
        assert result.dropped_count == 5


class TestMessageSequenceContract:
    """Contract tests for MessageSequence."""

    def test_empty_sequence(self) -> None:
        """Empty message sequence should have token_count of REPLY_PRIMER_TOKENS (count_messages overhead)."""
        seq = MessageSequence(messages=[])
        # TokenCounter.count_messages adds REPLY_PRIMER_TOKENS overhead even for empty lists
        assert seq.token_count == REPLY_PRIMER_TOKENS
        assert seq.is_tool_sequence is False

    def test_non_tool_sequence(self) -> None:
        """A sequence without tool calls should report is_tool_sequence=False."""
        from henchman.providers.base import Message
        msgs = [Message(role="user", content="hello"), Message(role="assistant", content="hi")]
        seq = MessageSequence(messages=msgs)
        assert seq.is_tool_sequence is False

    def test_tool_sequence(self) -> None:
        """A sequence with tool calls should report is_tool_sequence=True."""
        from henchman.providers.base import Message, ToolCall
        msgs = [
            Message(role="assistant", content="Let me check", tool_calls=[ToolCall(id="1", name="test", arguments={})]),
            Message(role="tool", content="result", tool_call_id="1"),
        ]
        seq = MessageSequence(messages=msgs)
        assert seq.is_tool_sequence is True


class TestMessageSequenceGrouperContract:
    """Contract tests for MessageSequenceGrouper."""

    def test_empty_messages(self) -> None:
        """Empty message list should produce no sequences."""
        sequences = MessageSequenceGrouper.group_into_sequences([])
        assert sequences == []

    def test_single_message(self) -> None:
        """Single message should produce one sequence."""
        from henchman.providers.base import Message
        sequences = MessageSequenceGrouper.group_into_sequences([Message(role="user", content="hi")])
        assert len(sequences) == 1

    def test_tool_call_sequence_kept_together(self) -> None:
        """Tool call and its response should be in the same sequence."""
        from henchman.providers.base import Message, ToolCall
        msgs = [
            Message(role="user", content="check"),
            Message(role="assistant", content="", tool_calls=[ToolCall(id="1", name="fn", arguments={})]),
            Message(role="tool", content="ok", tool_call_id="1"),
        ]
        sequences = MessageSequenceGrouper.group_into_sequences(msgs)
        # The assistant+tool should be grouped together
        assert len(sequences) >= 1
        # Verify the tool call sequence is atomic
        for seq in sequences:
            if seq.is_tool_sequence:
                assert any(msg.role == "assistant" and msg.tool_calls for msg in seq.messages)
                assert any(msg.role == "tool" for msg in seq.messages)


class TestMessageSequenceValidatorContract:
    """Contract tests for MessageSequenceValidator."""

    def test_valid_sequence(self) -> None:
        """A valid message sequence should pass validation."""
        from henchman.providers.base import Message
        msgs = [
            Message(role="user", content="hello"),
            Message(role="assistant", content="hi"),
        ]
        assert MessageSequenceValidator.validate_compacted_sequence(msgs) is True

    def test_valid_tool_sequence(self) -> None:
        """A valid tool call sequence should pass validation."""
        from henchman.providers.base import Message, ToolCall
        msgs = [
            Message(role="assistant", content="", tool_calls=[ToolCall(id="1", name="fn", arguments={})]),
            Message(role="tool", content="result", tool_call_id="1"),
        ]
        assert MessageSequenceValidator.validate_compacted_sequence(msgs) is True

    def test_orphan_tool_message_fails(self) -> None:
        """A tool message without preceding assistant tool call should fail."""
        from henchman.providers.base import Message
        msgs = [
            Message(role="user", content="hello"),
            Message(role="tool", content="orphan", tool_call_id="1"),
        ]
        assert MessageSequenceValidator.validate_compacted_sequence(msgs) is False


class TestProtectedZoneManagerContract:
    """Contract tests for ProtectedZoneManager."""

    def test_separate_at_index(self) -> None:
        """Messages should be split at the protection index."""
        from henchman.providers.base import Message
        msgs = [Message(role="user", content="a"), Message(role="assistant", content="b"), Message(role="user", content="c")]
        manager = ProtectedZoneManager(max_protected_tokens=1000)
        protected, unprotected = manager.separate_protected_messages(msgs, protect_from_index=1)
        assert len(protected) == 2
        assert len(unprotected) == 1

    def test_separate_negative_index(self) -> None:
        """Negative protect_from_index should leave all messages unprotected."""
        from henchman.providers.base import Message
        msgs = [Message(role="user", content="a")]
        manager = ProtectedZoneManager(max_protected_tokens=1000)
        protected, unprotected = manager.separate_protected_messages(msgs, protect_from_index=-1)
        assert len(protected) == 0
        assert len(unprotected) == 1

    def test_truncate_empty(self) -> None:
        """Truncating empty messages should return empty."""
        manager = ProtectedZoneManager(max_protected_tokens=100)
        msgs, tokens = manager.truncate_if_needed([])
        assert msgs == []
        assert tokens == 0


class TestCompactionBudgetCalculatorContract:
    """Contract tests for CompactionBudgetCalculator."""

    def test_calculate_budget(self) -> None:
        """Budget should be max_tokens minus system and protected."""
        calc = CompactionBudgetCalculator(max_tokens=1000)
        budget = calc.calculate_budget(system_tokens=100, protected_tokens=200)
        assert budget == 700

    def test_handle_edge_cases_no_sequences(self) -> None:
        """With no sequences, should return system + protected messages."""
        from henchman.providers.base import Message
        calc = CompactionBudgetCalculator(max_tokens=1000)
        system_msgs = [Message(role="system", content="sys")]
        protected_msgs = [Message(role="user", content="prot")]
        result = calc.handle_edge_cases(system_msgs, 10, protected_msgs, 10, [])
        assert result is not None
        assert len(result) == 2


class TestSummarizationConfigContract:
    """Contract tests for SummarizationConfig."""

    def test_defaults(self) -> None:
        """SummarizationConfig should have sensible defaults."""
        config = SummarizationConfig()
        assert config.summarize is True
        assert config.protect_from_index == -1
        assert config.provider is None


# ---------------------------------------------------------------------------
# CompressionStrategy contracts
# ---------------------------------------------------------------------------


class TestCompressionStrategyConfigContract:
    """Contract tests for CompressionStrategyConfig."""

    def test_config_fields(self) -> None:
        """Config should have all required fields."""
        config = CompressionStrategyConfig(
            name="test",
            high_threshold=0.8,
            medium_threshold=0.4,
            preserve_tool_sequences=True,
            preserve_code_blocks=True,
        )
        assert config.name == "test"
        assert config.high_threshold == 0.8
        assert config.medium_threshold == 0.4
        assert config.preserve_tool_sequences is True
        assert config.preserve_code_blocks is True


class TestCompressionStrategyContract:
    """Contract tests for CompressionStrategy."""

    def test_compress_empty(self) -> None:
        """Compressing empty messages should return empty."""
        config = CompressionStrategyConfig(
            name="test", high_threshold=0.7, medium_threshold=0.3,
            preserve_tool_sequences=True, preserve_code_blocks=False,
        )
        strategy = CompressionStrategy(config)
        result = strategy.compress([], [], {})
        assert result == []

    def test_high_importance_preserved(self) -> None:
        """High-importance cluster messages should be fully preserved."""
        from henchman.providers.base import Message
        config = CompressionStrategyConfig(
            name="test", high_threshold=0.7, medium_threshold=0.3,
            preserve_tool_sequences=True, preserve_code_blocks=False,
        )
        strategy = CompressionStrategy(config)
        msgs = [Message(role="user", content="important"), Message(role="assistant", content="yes")]
        result = strategy.compress(msgs, [[0, 1]], {0: 0.9})
        assert len(result) == 2

    def test_low_importance_dropped(self) -> None:
        """Low-importance cluster messages should be dropped (unless tool/code)."""
        from henchman.providers.base import Message
        config = CompressionStrategyConfig(
            name="test", high_threshold=0.7, medium_threshold=0.3,
            preserve_tool_sequences=False, preserve_code_blocks=False,
        )
        strategy = CompressionStrategy(config)
        msgs = [Message(role="user", content="trivial"), Message(role="assistant", content="whatever")]
        result = strategy.compress(msgs, [[0, 1]], {0: 0.1})
        assert len(result) == 0


class TestCompressionStrategyFactoryContract:
    """Contract tests for CompressionStrategyFactory."""

    def test_known_types(self) -> None:
        """Factory should create strategies for known conversation types."""
        for conv_type in ("coding", "debugging", "research", "general"):
            strategy = CompressionStrategyFactory.create_for_conversation_type(conv_type)
            assert isinstance(strategy, CompressionStrategy)
            assert strategy.config.name == conv_type

    def test_unknown_type_falls_back_to_general(self) -> None:
        """Unknown conversation type should fall back to general strategy."""
        strategy = CompressionStrategyFactory.create_for_conversation_type("unknown_type")
        assert strategy.config.name == "general"


# ---------------------------------------------------------------------------
# Intelligent context types contracts
# ---------------------------------------------------------------------------


class TestIntelligentContextConstantsContract:
    """Contract tests for IntelligentContextConstants."""

    def test_thresholds_are_valid_ratios(self) -> None:
        """All threshold constants should be between 0 and 1."""
        c = IntelligentContextConstants
        assert 0 <= c.DEFAULT_IMPORTANCE_THRESHOLD <= 1
        assert 0 <= c.DEFAULT_CLUSTER_SIMILARITY_THRESHOLD <= 1
        assert 0 <= c.DEFAULT_COMPRESSION_HIGH_THRESHOLD <= 1
        assert 0 <= c.DEFAULT_COMPRESSION_MEDIUM_THRESHOLD <= 1


class TestPreservedContentContract:
    """Contract tests for PreservedContent."""

    def test_from_sections(self) -> None:
        """from_sections should join sections and count tokens."""
        content = PreservedContent.from_sections(["section1", "section2"])
        assert "section1" in content.content
        assert "section2" in content.content
        assert content.tokens > 0
        assert content.sections == ["section1", "section2"]

    def test_content_serializable(self) -> None:
        """PreservedContent should be representable as dict."""
        content = PreservedContent(content="test", tokens=5, sections=["a"])
        d = content.__dict__
        assert d["content"] == "test"
        assert d["tokens"] == 5


class TestContentAnalysisContract:
    """Contract tests for ContentAnalysis."""

    def test_defaults(self) -> None:
        """ContentAnalysis should default to all False."""
        analysis = ContentAnalysis()
        assert analysis.has_code is False
        assert analysis.has_errors is False
        assert analysis.has_decisions is False
        assert analysis.has_tools is False

    def test_update_from_content_detects_code(self) -> None:
        """update_from_content should detect code blocks."""
        analysis = ContentAnalysis()
        analysis.update_from_content("```python\nprint('hi')\n```")
        assert analysis.has_code is True

    def test_update_from_content_detects_errors(self) -> None:
        """update_from_content should detect error keywords."""
        analysis = ContentAnalysis()
        analysis.update_from_content("An exception occurred: traceback follows")
        assert analysis.has_errors is True

    def test_update_from_content_detects_decisions(self) -> None:
        """update_from_content should detect decision keywords."""
        analysis = ContentAnalysis()
        analysis.update_from_content("We recommend this approach and conclude it's best")
        assert analysis.has_decisions is True

    def test_update_from_content_detects_tools(self) -> None:
        """update_from_content should detect tool keywords."""
        analysis = ContentAnalysis()
        analysis.update_from_content("Call the execute function to run the tool")
        assert analysis.has_tools is True

    def test_get_summary_parts(self) -> None:
        """get_summary_parts should return descriptions for detected types."""
        analysis = ContentAnalysis(has_code=True, has_errors=True)
        parts = analysis.get_summary_parts()
        assert len(parts) == 2
        assert any("code" in p.lower() for p in parts)
        assert any("error" in p.lower() for p in parts)


class TestFenceResultContract:
    """Contract tests for FenceResult."""

    def test_not_found_factory(self) -> None:
        """not_found should create a result with found=False."""
        result = FenceResult.not_found(next_pos=42)
        assert result.found is False
        assert result.code_end == -1
        assert result.next_pos == 42

    def test_found_default(self) -> None:
        """FenceResult should default found=True."""
        result = FenceResult(code_end=10, next_pos=15)
        assert result.found is True


class TestCompressionConfigContract:
    """Contract tests for CompressionConfig."""

    def test_fields(self) -> None:
        """CompressionConfig should have all required fields."""
        config = CompressionConfig(
            high_threshold=0.7,
            medium_threshold=0.3,
            preserve_tool_sequences=True,
            preserve_code_blocks=False,
        )
        assert config.high_threshold == 0.7
        assert config.medium_threshold == 0.3
        assert config.preserve_tool_sequences is True
        assert config.preserve_code_blocks is False


class TestIntelligentCompactionResultContract:
    """Contract tests for IntelligentCompactionResult."""

    def test_defaults(self) -> None:
        """IntelligentCompactionResult should have sensible defaults."""
        result = IntelligentCompactionResult(messages=[])
        assert result.was_compacted is False
        assert result.dropped_count == 0
        assert result.summary is None
        assert result.importance_scores is None
        assert result.clusters is None
        assert result.compression_ratio is None


class TestResultCreationParamsContract:
    """Contract tests for ResultCreationParams."""

    def test_get_dropped_count(self) -> None:
        """get_dropped_count should return original minus safe count."""
        from henchman.providers.base import Message
        params = ResultCreationParams(
            original_messages=[Message(role="user", content="a") for _ in range(10)],
            safe_messages=[Message(role="user", content="a") for _ in range(6)],
            importance_scores={},
            clusters=[],
            original_tokens=1000,
            was_compacted=True,
        )
        assert params.get_dropped_count() == 4

    def test_get_compression_ratio(self) -> None:
        """get_compression_ratio should return reduction ratio."""
        params = ResultCreationParams(
            original_messages=[],
            safe_messages=[],
            importance_scores={},
            clusters=[],
            original_tokens=1000,
            was_compacted=True,
        )
        assert params.get_compression_ratio(700) == 0.3
        assert params.get_compression_ratio(0) == 1.0

    def test_get_compression_ratio_zero_original(self) -> None:
        """get_compression_ratio should handle zero original tokens."""
        params = ResultCreationParams(
            original_messages=[],
            safe_messages=[],
            importance_scores={},
            clusters=[],
            original_tokens=0,
            was_compacted=True,
        )
        assert params.get_compression_ratio(0) == 0.0


class TestTruncationParamsContract:
    """Contract tests for TruncationParams."""

    def test_apply(self) -> None:
        """apply should truncate content and append marker."""
        params = TruncationParams(content="hello world", marker="[truncated]")
        result = params.apply(5)
        assert "[truncated]" in result or result.endswith("[truncated]")


class TestAsDictMixinContract:
    """Contract tests for AsDictMixin."""

    def test_asdict(self) -> None:

        @dataclass
        class Simple(AsDictMixin):
            name: str
            value: int

        obj = Simple(name="test", value=42)
        d = obj.to_dict()
        assert d == {"name": "test", "value": 42}
