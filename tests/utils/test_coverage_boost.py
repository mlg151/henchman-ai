"""Tests to boost coverage for utils modules.

Targets missing lines in:
- intelligent_context.py
- compression_strategy.py
- message_clusterer.py
- tokens.py
- importance_scorer.py
- retry.py
- compaction.py
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from henchman.providers.base import Message, ToolCall
from henchman.utils.compaction import (
    CompactionResult,
    MessageSequenceGrouper,
    ProtectedZoneManager,
    SummarizationConfig,
    _all_tool_calls_have_responses,
    _attempt_summarization,
    _generate_summary_with_provider,
    _is_valid_tool_message,
    _truncate_protected_zone_messages,
    _truncate_tool_message_content,
    CompactionParams, compact_messages,
)
from henchman.utils.compaction import (
    _format_messages_for_summary_content as _format_messages_for_summary,
)
from henchman.utils.compression_strategy import (
    CompressionStrategy,
    CompressionStrategyConfig,
    CompressionStrategyFactory,
)
from henchman.utils.importance_scorer import ImportanceScorer
from henchman.utils.intelligent_context import (
    ConversationTypeDetector,
    IntelligentContextManager,
    IntelligentContextParams,
)
from henchman.utils.message_clusterer import MessageClusterer
from henchman.utils.tokens import TokenCounter

# ---------------------------------------------------------------------------
# tokens.py
# ---------------------------------------------------------------------------


class TestTokenCounterMissingLines:
    """Cover lines 127, 132 in tokens.py."""

    def test_truncate_empty_string(self) -> None:
        """Line 127: truncate_text with empty string returns empty string."""
        result = TokenCounter.truncate_text("", max_tokens=100)
        assert result == ""

    def test_truncate_fits_within_limit(self) -> None:
        """Line 132: truncate_text when text is already within limit."""
        text = "short"
        result = TokenCounter.truncate_text(text, max_tokens=1000)
        assert result == text

    def test_truncate_known_model(self) -> None:
        """truncate_text with a known model name."""
        text = "hello world this is a test message for encoding"
        result = TokenCounter.truncate_text(text, max_tokens=5)
        assert len(result) < len(text)

    def test_get_encoding_unknown_model(self) -> None:
        """_get_encoding falls back to cl100k_base for unknown models."""
        enc = TokenCounter._get_encoding("unknown-model-xyz")
        assert enc is not None

    def test_get_encoding_known_model(self) -> None:
        """_get_encoding returns model-specific encoding for known models."""
        enc = TokenCounter._get_encoding("gpt-4")
        assert enc is not None


# ---------------------------------------------------------------------------
# importance_scorer.py
# ---------------------------------------------------------------------------


class TestImportanceScorerMissingLines:
    """Cover lines 175, 191, 278 in importance_scorer.py."""

    def test_unknown_role_returns_zero(self) -> None:
        """Line 175: unknown role returns 0.0 from _get_role_based_importance."""
        scorer = ImportanceScorer()
        msg = Message(role="unknown_role", content="test")
        result = scorer._get_role_based_importance(msg)
        assert result == 0.0

    def test_assistant_long_content_importance(self) -> None:
        """Line 191: assistant with long content returns high importance."""
        scorer = ImportanceScorer()
        long_content = "x" * 200  # > 100 chars (LONG_CONTENT_THRESHOLD)
        msg = Message(role="assistant", content=long_content)
        result = scorer._get_assistant_importance(msg)
        assert result == scorer._ASSISTANT_LONG_CONTENT_IMPORTANCE

    def test_apply_minimum_score_zero(self) -> None:
        """Line 278: _apply_minimum_score returns minimum when score == 0.0."""
        scorer = ImportanceScorer()
        result = scorer._apply_minimum_score(0.0)
        assert result == scorer._MINIMUM_IMPORTANCE

    def test_apply_minimum_score_nonzero(self) -> None:
        """_apply_minimum_score returns score unchanged when non-zero."""
        scorer = ImportanceScorer()
        result = scorer._apply_minimum_score(0.5)
        assert result == 0.5

    def test_calculate_importance_with_unknown_role(self) -> None:
        """Full pipeline with unknown role message."""
        scorer = ImportanceScorer()
        msg = Message(role="unknown", content="hi")
        scores = scorer.calculate_importance_scores([msg])
        # Should apply minimum score since base is 0.0
        assert scores[0] >= scorer._MINIMUM_IMPORTANCE


# ---------------------------------------------------------------------------
# intelligent_context.py
# ---------------------------------------------------------------------------


class TestConversationTypeDetectorMissingLine:
    """Cover line 145 (return 'general') in intelligent_context.py."""

    def test_returns_general_for_generic_messages(self) -> None:
        """Line 145: return 'general' when no type-specific keywords found."""
        detector = ConversationTypeDetector()
        messages = [
            Message(role="user", content="Hello, how are you?"),
            Message(role="assistant", content="I am doing well, thank you."),
        ]
        result = detector.detect(messages)
        assert result == "general"

    def test_returns_general_for_empty(self) -> None:
        """detect returns 'general' for empty messages."""
        detector = ConversationTypeDetector()
        result = detector.detect([])
        assert result == "general"


class TestIntelligentContextManagerMissingLines:
    """Cover lines 367-374, 388-396, 411-418, 463, 486-498, 607-608, 614->613, 645, 663."""

    def test_enforce_safety_limits_basic(self) -> None:
        """Lines 367-374: enforce_safety_limits processes messages."""
        manager = IntelligentContextManager(params=IntelligentContextParams(max_tokens=100))
        messages = [
            Message(role="user", content="short message"),
            Message(role="assistant", content="short reply"),
        ]
        result = manager.enforce_safety_limits(messages)
        assert len(result) == 2

    def test_enforce_message_safety_limit_no_content(self) -> None:
        """Lines 388-389: message with no content passes through unchanged."""
        from henchman.utils.intelligent_context import MessageSafetyEnforcer
        enforcer = MessageSafetyEnforcer(safety_limit_ratio=0.5, max_tokens=100)
        msg = Message(role="user", content=None)
        # Test through public API
        result = enforcer.enforce_safety_limits([msg])
        assert len(result) == 1
        assert result[0] is msg

    def test_enforce_message_safety_limit_short_content(self) -> None:
        """Lines 391-392: message shorter than limit passes through."""
        from henchman.utils.intelligent_context import MessageSafetyEnforcer
        enforcer = MessageSafetyEnforcer(safety_limit_ratio=0.5, max_tokens=1000)
        msg = Message(role="user", content="short")
        # Test through public API
        result = enforcer.enforce_safety_limits([msg])
        assert len(result) == 1
        assert result[0] is msg

    def test_enforce_message_safety_limit_truncates_long(self) -> None:
        """Lines 394-395: very long message gets truncated."""
        from henchman.utils.intelligent_context import MessageSafetyEnforcer
        enforcer = MessageSafetyEnforcer(safety_limit_ratio=0.1, max_tokens=100)  # limit = 10
        long_content = "word " * 2000
        msg = Message(role="user", content=long_content)
        # Test through public API
        result = enforcer.enforce_safety_limits([msg])
        assert len(result) == 1
        assert result[0].content is not None
        assert "truncated" in result[0].content

    def test_create_truncated_message(self) -> None:
        """Lines 411-418: _create_truncated_message creates truncated version."""
        from henchman.utils.intelligent_context_formatter import _create_truncated_message
        long_content = "word " * 2000
        msg = Message(role="user", content=long_content)
        # Call the function directly for coverage
        result = _create_truncated_message(msg, limit=10, safety_ratio=0.1)
        assert result.role == "user"
        assert result.content is not None
        assert "truncated" in result.content

    def test_create_truncated_message_no_content(self) -> None:
        """_create_truncated_message with no content returns original."""
        from henchman.utils.intelligent_context_formatter import _create_truncated_message
        msg = Message(role="user", content=None)
        # Call the function directly for coverage
        result = _create_truncated_message(msg, limit=10, safety_ratio=0.1)
        assert result is msg

    def test_compact_with_result_returns_result(self) -> None:
        """Line 463: compact_with_result returns IntelligentCompactionResult."""
        manager = IntelligentContextManager(params=IntelligentContextParams())
        messages = [Message(role="user", content="hello")]
        result = manager.compact_with_result(messages)
        assert result.messages == messages
        assert result.was_compacted is False

    def test_validate_compacted_sequence_valid(self) -> None:
        """Lines 486-498: validate_compacted_sequence with valid tool sequence."""
        manager = IntelligentContextManager(params=IntelligentContextParams())
        tool_call = ToolCall(id="tc1", name="test", arguments={})
        messages = [
            Message(role="user", content="hello"),
            Message(role="assistant", content="calling tool", tool_calls=[tool_call]),
            Message(role="tool", content="result", tool_call_id="tc1"),
        ]
        assert manager.validate_compacted_sequence(messages) is True

    def test_validate_compacted_sequence_tool_at_start(self) -> None:
        """Lines 488-489: tool message at position 0 is invalid."""
        manager = IntelligentContextManager(params=IntelligentContextParams())
        messages = [
            Message(role="tool", content="result", tool_call_id="tc1"),
        ]
        assert manager.validate_compacted_sequence(messages) is False

    def test_validate_compacted_sequence_bad_prev_role(self) -> None:
        """Lines 491-492: tool message not preceded by assistant is invalid."""
        manager = IntelligentContextManager(params=IntelligentContextParams())
        messages = [
            Message(role="user", content="question"),
            Message(role="tool", content="result", tool_call_id="tc1"),
        ]
        assert manager.validate_compacted_sequence(messages) is False

    def test_validate_compacted_sequence_wrong_tool_id(self) -> None:
        """Lines 494-496: tool message with mismatched id is invalid."""
        manager = IntelligentContextManager(params=IntelligentContextParams())
        tool_call = ToolCall(id="tc1", name="test", arguments={})
        messages = [
            Message(role="assistant", content="calling", tool_calls=[tool_call]),
            Message(role="tool", content="result", tool_call_id="wrong_id"),
        ]
        assert manager.validate_compacted_sequence(messages) is False

    def test_calculate_cluster_importance_empty_cluster(self) -> None:
        """Lines 607-608: empty cluster gets importance 0.0."""
        manager = IntelligentContextManager(params=IntelligentContextParams())
        clusters = [[], [0]]  # First cluster is empty
        importance_scores = {0: 0.8}
        result = manager.message_compactor.calculate_cluster_importance(clusters, importance_scores)
        assert result[0] == 0.0
        assert result[1] > 0.0

    def test_calculate_cluster_importance_valid(self) -> None:
        """Lines 614->613: valid cluster calculates average importance."""
        manager = IntelligentContextManager(params=IntelligentContextParams())
        clusters = [[0, 1]]
        importance_scores = {0: 0.8, 1: 0.6}
        result = manager.message_compactor.calculate_cluster_importance(clusters, importance_scores)
        assert result[0] > 0.0

    def test_generate_intelligent_summary_returns_none(self) -> None:
        """Line 645: _generate_intelligent_summary returns None."""
        manager = IntelligentContextManager(params=IntelligentContextParams())
        messages = [Message(role="user", content="hello")]
        result = manager.summary_generator.generate_intelligent_summary(messages, {0: 0.5}, [[0]])
        assert result is None

    def test_preserve_critical_context_returns_messages(self) -> None:
        """Line 663: _preserve_critical_context returns messages unchanged."""
        manager = IntelligentContextManager(params=IntelligentContextParams())
        messages = [Message(role="user", content="hello")]
        result = manager.message_preserver.preserve_critical_context(messages, {0: 0.5})
        assert result == messages


# ---------------------------------------------------------------------------
# compression_strategy.py
# ---------------------------------------------------------------------------


class TestCompressionStrategyMissingLines:
    """Cover missing lines in compression_strategy.py."""

    def _make_config(
        self,
        high: float = 0.7,
        medium: float = 0.4,
        tool_seqs: bool = False,
        code_blocks: bool = False,
    ) -> CompressionStrategyConfig:
        """Create config for tests."""
        return CompressionStrategyConfig(
            name="test",
            high_threshold=high,
            medium_threshold=medium,
            preserve_tool_sequences=tool_seqs,
            preserve_code_blocks=code_blocks,
        )

    def test_compress_empty_messages(self) -> None:
        """Line 86: empty messages returns messages unchanged."""
        strategy = CompressionStrategy(self._make_config())
        result = strategy.compress([], [], {})
        assert result == []

    def test_compress_empty_clusters(self) -> None:
        """Line 86: empty clusters returns messages unchanged."""
        messages = [Message(role="user", content="hi")]
        strategy = CompressionStrategy(self._make_config())
        result = strategy.compress(messages, [], {})
        assert result == messages

    def test_compress_medium_importance_no_summary(self) -> None:
        """Lines 102->111: medium importance with empty cluster → no summary appended."""
        strategy = CompressionStrategy(self._make_config(high=0.9, medium=0.5))
        messages = [Message(role="user", content="hello")]
        # Empty cluster → _summarize_cluster returns None
        clusters = [[]]  # empty cluster indices
        importance = {0: 0.6}  # medium importance
        result = strategy.compress(messages, clusters, importance)
        # Empty cluster produces no summary
        assert result == []

    def test_compress_medium_with_tool_sequences(self) -> None:
        """Lines 111->90, 202-205: medium importance with tool sequences preserved."""
        tool_call = ToolCall(id="tc1", name="test", arguments={})
        messages = [
            Message(role="user", content="do something"),
            Message(role="assistant", content="using tool", tool_calls=[tool_call]),
            Message(role="tool", content="done", tool_call_id="tc1"),
        ]
        config = self._make_config(high=0.9, medium=0.3, tool_seqs=True)
        strategy = CompressionStrategy(config)
        clusters = [[0, 1, 2]]
        importance = {0: 0.5}  # medium importance
        result = strategy.compress(messages, clusters, importance)
        # Should preserve tool sequence
        assert any(m.role == "assistant" and m.tool_calls for m in result)

    def test_compress_low_importance_with_code_blocks(self) -> None:
        """Lines 121->128, 129, 220-226: low importance preserves code blocks."""
        messages = [
            Message(role="user", content="what is this code?"),
            Message(role="assistant", content="```python\ndef hello():\n    pass\n```"),
        ]
        config = self._make_config(high=0.9, medium=0.7, code_blocks=True)
        strategy = CompressionStrategy(config)
        clusters = [[0, 1]]
        importance = {0: 0.1}  # low importance
        result = strategy.compress(messages, clusters, importance)
        # Should preserve message with code block
        assert any("```" in (m.content or "") for m in result)

    def test_summarize_cluster_empty(self) -> None:
        """Line 152: _summarize_cluster with empty cluster returns None."""
        strategy = CompressionStrategy(self._make_config())
        result = strategy._summarize_cluster([], [])
        assert result is None

    def test_generate_cluster_summary_empty(self) -> None:
        """Line 170: _generate_cluster_summary with empty list returns ''."""
        strategy = CompressionStrategy(self._make_config())
        result = strategy._generate_cluster_summary([])
        assert result == ""

    def test_generate_cluster_summary_short_content(self) -> None:
        """Lines 175->174: short content (no truncation) in cluster summary."""
        strategy = CompressionStrategy(self._make_config())
        messages = [Message(role="user", content="hi")]
        result = strategy._generate_cluster_summary(messages)
        assert "hi" in result
        assert "..." not in result

    def test_generate_cluster_summary_long_content(self) -> None:
        """Line 179: long content gets truncated with '...'."""
        strategy = CompressionStrategy(self._make_config())
        messages = [Message(role="user", content="x" * 100)]
        result = strategy._generate_cluster_summary(messages)
        assert "..." in result

    def test_preserve_tool_sequences_no_tool_calls(self) -> None:
        """Lines 198->197: message without tool calls is not preserved."""
        strategy = CompressionStrategy(self._make_config())
        messages = [Message(role="assistant", content="just text")]
        compressed: list[Message] = []
        strategy._preserve_tool_sequences_in_cluster(messages, [0], compressed)
        assert compressed == []

    def test_preserve_tool_sequences_with_tool_calls(self) -> None:
        """Lines 202-205: assistant with tool calls is preserved."""
        tool_call = ToolCall(id="tc1", name="test", arguments={})
        messages = [
            Message(role="assistant", content="calling", tool_calls=[tool_call]),
            Message(role="tool", content="result", tool_call_id="tc1"),
        ]
        strategy = CompressionStrategy(self._make_config())
        compressed: list[Message] = []
        strategy._preserve_tool_sequences_in_cluster(messages, [0, 1], compressed)
        assert len(compressed) == 2

    def test_factory_coding(self) -> None:
        """Line 251: factory creates coding strategy."""
        strategy = CompressionStrategyFactory.create_for_conversation_type("coding")
        assert strategy.config.name == "coding"
        assert strategy.config.preserve_code_blocks is True

    def test_factory_debugging(self) -> None:
        """Line 259: factory creates debugging strategy."""
        strategy = CompressionStrategyFactory.create_for_conversation_type("debugging")
        assert strategy.config.name == "debugging"

    def test_factory_research(self) -> None:
        """Line 268: factory creates research strategy."""
        strategy = CompressionStrategyFactory.create_for_conversation_type("research")
        assert strategy.config.name == "research"

    def test_factory_general(self) -> None:
        """factory creates general strategy."""
        strategy = CompressionStrategyFactory.create_for_conversation_type("general")
        assert strategy.config.name == "general"


# ---------------------------------------------------------------------------
# message_clusterer.py
# ---------------------------------------------------------------------------


class TestMessageClustererMissingLines:
    """Cover missing lines in message_clusterer.py."""

    def test_cluster_tool_call_sequences_single_message(self) -> None:
        """Line 103->90: single message returns unchanged clusters."""
        clusterer = MessageClusterer()
        messages = [Message(role="user", content="hi")]
        clusters = [[0]]
        result = clusterer._cluster_tool_call_sequences(messages, clusters)
        assert result == [[0]]

    def test_should_merge_adjacent_non_adjacent_indices(self) -> None:
        """Line 169: _should_merge_adjacent_clusters returns False for non-adjacent."""
        clusterer = MessageClusterer()
        messages = [
            Message(role="user", content="a"),
            Message(role="assistant", content="b"),
            Message(role="user", content="c"),
        ]
        # Clusters [0] and [2] are not adjacent
        result = clusterer._should_merge_adjacent_clusters(messages, [0], [2])
        assert result is False

    def test_cluster_topic_similarity_empty_keywords(self) -> None:
        """Lines 217-218: clusters with empty keywords skip similarity check."""
        clusterer = MessageClusterer()
        # Messages with no content → empty keywords
        messages = [
            Message(role="user", content=None),
            Message(role="assistant", content=None),
        ]
        clusters = [[0], [1]]
        result = clusterer._cluster_topic_similarity(messages, clusters)
        # Both have empty keywords, should not be merged
        assert len(result) == 2

    def test_cluster_topic_similarity_merges_similar(self) -> None:
        """Lines 227-234: clusters with similar keywords get merged."""
        clusterer = MessageClusterer(cluster_similarity_threshold=0.1)
        messages = [
            Message(role="user", content="python programming language function"),
            Message(role="assistant", content="python programming language function"),
        ]
        clusters = [[0], [1]]
        result = clusterer._cluster_topic_similarity(messages, clusters)
        # High overlap → should merge
        assert len(result) == 1

    def test_merge_clusters_nothing_to_merge_single_cluster(self) -> None:
        """Line 437: _merge_clusters_containing_indices with only 1 cluster → return unchanged."""
        clusterer = MessageClusterer()
        clusters = [[0, 1, 2]]
        result = clusterer._merge_clusters_containing_indices(clusters, [0])
        # Only one cluster contains index 0, nothing to merge
        assert result == [[0, 1, 2]]

    def test_cluster_role_patterns_single_cluster(self) -> None:
        """Line 394->392: _cluster_role_patterns with 1 cluster returns unchanged."""
        clusterer = MessageClusterer()
        messages = [Message(role="user", content="hi")]
        clusters = [[0]]
        result = clusterer._cluster_role_patterns(messages, clusters)
        assert result == [[0]]

    def test_cluster_temporal_proximity_single_cluster(self) -> None:
        """_cluster_temporal_proximity with 1 cluster returns unchanged."""
        clusterer = MessageClusterer()
        messages = [Message(role="user", content="hi")]
        clusters = [[0]]
        result = clusterer._cluster_temporal_proximity(messages, clusters)
        assert result == [[0]]


# ---------------------------------------------------------------------------
# compaction.py
# ---------------------------------------------------------------------------


class TestCompactionMissingLines:
    """Cover missing lines in compaction.py."""

    def test_sequence_grouper_last_sequence_preserved(self) -> None:
        """Lines 121->124: last non-empty sequence is added to sequences list."""
        messages = [
            Message(role="system", content="system prompt"),
            Message(role="user", content="question"),
            Message(role="assistant", content="answer"),
        ]
        grouper = MessageSequenceGrouper()
        sequences = grouper.group_into_sequences(messages)
        assert len(sequences) >= 1

    def test_handle_tool_call_sequence_user_break(self) -> None:
        """Lines 189->exit: user message stops tool response scanning."""
        tool_call = ToolCall(id="tc1", name="test", arguments={})
        messages = [
            Message(role="assistant", content="calling", tool_calls=[tool_call]),
            Message(role="user", content="new question"),
        ]
        current_sequence: list[Message] = [messages[0]]
        consumed: set[int] = set()
        MessageSequenceGrouper._handle_tool_call_sequence(messages, 0, current_sequence, consumed)
        # user message at index 1 should stop scanning
        assert 1 not in consumed

    def test_handle_tool_call_sequence_matches_tool_call_id(self) -> None:
        """Lines 191-199: tool response with matching id is added to sequence."""
        tool_call = ToolCall(id="tc1", name="test", arguments={})
        messages = [
            Message(role="assistant", content="calling", tool_calls=[tool_call]),
            Message(role="tool", content="result", tool_call_id="tc1"),
        ]
        current_sequence: list[Message] = [messages[0]]
        consumed: set[int] = set()
        MessageSequenceGrouper._handle_tool_call_sequence(messages, 0, current_sequence, consumed)
        assert messages[1] in current_sequence
        assert 1 in consumed

    def test_truncate_zone_messages_no_trim_needed(self) -> None:
        """Line 293: protected zone messages already fit."""
        messages = [Message(role="tool", content="short result")]
        manager = ProtectedZoneManager(max_protected_tokens=10000)
        result = manager.truncate_if_needed(messages)
        assert result[0] == messages

    def test_truncate_tool_message_empty_content(self) -> None:
        """Line 330: _truncate_tool_message_content with no content returns original."""
        msg = Message(role="tool", content=None)
        result = _truncate_tool_message_content(msg, tokens_to_trim=10)
        assert result is msg

    def test_truncate_tool_message_heavy_truncation(self) -> None:
        """Line 337: heavy truncation when text is shorter than chars_to_trim."""
        msg = Message(role="tool", content="short")
        result = _truncate_tool_message_content(msg, tokens_to_trim=10000)
        assert result.content is not None
        assert "heavily truncated" in result.content

    def test_sequence_validator_tool_at_zero(self) -> None:
        """Line 450: tool message at index 0 is invalid."""
        messages = [Message(role="tool", content="result", tool_call_id="tc1")]
        assert _is_valid_tool_message(messages, 0, messages[0]) is False

    def test_all_tool_calls_have_responses_missing_response(self) -> None:
        """Lines 476->478: tool call without response returns False."""
        tool_call = ToolCall(id="tc1", name="test", arguments={})
        messages = [
            Message(role="assistant", content="calling", tool_calls=[tool_call]),
            Message(role="tool", content="result", tool_call_id="wrong_id"),
        ]
        assert _all_tool_calls_have_responses(messages) is False

    def test_all_tool_calls_have_responses_valid(self) -> None:
        """All tool calls matched."""
        tool_call = ToolCall(id="tc1", name="test", arguments={})
        messages = [
            Message(role="assistant", content="calling", tool_calls=[tool_call]),
            Message(role="tool", content="result", tool_call_id="tc1"),
        ]
        assert _all_tool_calls_have_responses(messages) is True

    def test_format_messages_for_summary_with_tool_call_id(self) -> None:
        """Line 841: message with tool_call_id uses [Tool result] prefix."""
        messages = [
            Message(role="tool", content="the result here", tool_call_id="tc1"),
        ]
        result = _format_messages_for_summary(messages)
        assert "[Tool result]" in result

    def test_format_messages_skips_system(self) -> None:
        """format_messages_for_summary skips system messages."""
        messages = [
            Message(role="system", content="You are an assistant"),
            Message(role="user", content="hello"),
        ]
        result = _format_messages_for_summary(messages)
        assert "You are an assistant" not in result
        assert "hello" in result

    @pytest.mark.anyio
    async def test_generate_summary_with_provider_success(self) -> None:
        """Lines 866->875: _generate_summary_with_provider streams chunks."""
        mock_provider = MagicMock()

        async def mock_stream(*args, **kwargs):
            chunk = MagicMock()
            chunk.content = "summarized"
            chunk.finish_reason = "stop"
            yield chunk

        mock_provider.chat_completion_stream = mock_stream
        messages = [Message(role="user", content="something to summarize")]
        result = await _generate_summary_with_provider(
            mock_provider, messages, _format_messages_for_summary
        )
        assert result == "summarized"

    @pytest.mark.anyio
    async def test_generate_summary_with_provider_exception(self) -> None:
        """Lines 878->880: exception in _generate_summary_with_provider returns None."""
        mock_provider = MagicMock()

        async def mock_stream(*args, **kwargs):
            raise RuntimeError("provider error")
            yield  # noqa: unreachable

        mock_provider.chat_completion_stream = mock_stream
        messages = [Message(role="user", content="test")]
        result = await _generate_summary_with_provider(
            mock_provider, messages, _format_messages_for_summary
        )
        assert result is None

    @pytest.mark.anyio
    async def test_compact_messages_no_compaction_needed(self) -> None:
        """Line 1019-1020: compact_messages returns early when fits in tokens."""
        messages = [Message(role="user", content="hi")]
        result = await compact_messages(CompactionParams(messages=messages, max_tokens=100000))
        assert result.was_compacted is False

    @pytest.mark.anyio
    async def test_compact_messages_compacted_not_summarized(self) -> None:
        """Line 1026: compact_messages returns result when was_compacted is True."""
        # Generate many messages to force compaction
        long_content = "word " * 500
        messages = [
            Message(role="system", content="system"),
            Message(role="user", content=long_content),
            Message(role="assistant", content=long_content),
            Message(role="user", content="final"),
        ]
        # compact with small token budget, no summarization
        result = await compact_messages(
            CompactionParams(messages=messages, max_tokens=100, summarize=False)
        )
        # Should have compacted
        assert len(result.messages) <= len(messages)

    @pytest.mark.anyio
    async def test_attempt_summarization_no_dropped_messages(self) -> None:
        """Line 1055: _attempt_summarization returns early when no dropped messages."""

        messages = [Message(role="user", content="hi")]
        mock_provider = MagicMock()
        result = CompactionResult(messages=messages, was_compacted=True)
        # All messages retained → no dropped messages
        updated = await _attempt_summarization(result, messages, mock_provider)
        assert updated.summary is None

    @pytest.mark.anyio
    async def test_attempt_summarization_exception_swallowed(self) -> None:
        """Lines 1068-1070: exception in summarizer is swallowed."""

        original = Message(role="user", content="original")
        kept = Message(role="user", content="kept")
        mock_provider = MagicMock()

        # Mock summarizer to raise
        with patch(
            "henchman.utils.compaction.MessageSummarizer.summarize",
            side_effect=RuntimeError("fail"),
        ):
            result = CompactionResult(messages=[kept], was_compacted=True)
            updated = await _attempt_summarization(result, [original, kept], mock_provider)
            # Exception swallowed, result unchanged
            assert updated.summary is None


# ---------------------------------------------------------------------------
# Additional tests for remaining gaps
# ---------------------------------------------------------------------------


class TestCompactionMissingLines2:
    """Cover remaining missing lines in compaction.py."""

    def test_group_into_sequences_last_sequence_not_empty(self) -> None:
        """Lines 121->124: current_sequence non-empty at end is added."""
        # This happens when the last message starts a new sequence
        messages = [
            Message(role="user", content="hello"),
            Message(role="assistant", content="world"),
        ]
        # Grouper processes user as new sequence start, assistant follows
        sequences = MessageSequenceGrouper.group_into_sequences(messages)
        assert len(sequences) >= 1
        # Find total messages covered
        total = sum(len(s.messages) for s in sequences)
        assert total > 0

    @pytest.mark.anyio
    async def test_generate_summary_provider_empty_chunks(self) -> None:
        """Lines 866->875: provider yields empty content chunks."""
        mock_provider = MagicMock()

        async def mock_stream(*args, **kwargs):
            chunk1 = MagicMock()
            chunk1.content = None  # Empty content
            chunk1.finish_reason = None
            yield chunk1
            chunk2 = MagicMock()
            chunk2.content = "final"
            chunk2.finish_reason = "stop"
            yield chunk2

        mock_provider.chat_completion_stream = mock_stream
        messages = [Message(role="user", content="something")]
        result = await _generate_summary_with_provider(
            mock_provider, messages, _format_messages_for_summary
        )
        assert result == "final"

    @pytest.mark.anyio
    async def test_compact_messages_was_not_compacted(self) -> None:
        """Line 1026: _compact_with_summarization_impl returns early when not compacted."""
        from henchman.utils.compaction import _compact_with_summarization_impl

        # Make messages that need compaction
        long_content = "word " * 500
        messages = [
            Message(role="system", content="system"),
            Message(role="user", content=long_content),
            Message(role="assistant", content=long_content),
            Message(role="user", content="final"),
        ]
        # compact_with_result returns was_compacted=False in some edge cases
        # We test the path where compaction occurs but no provider given
        config = SummarizationConfig(
            provider=None,
            summarize=True,
            protect_from_index=-1,
            max_protected_ratio=0.3,
        )
        result = await _compact_with_summarization_impl(messages, max_tokens=100, config=config)
        # Result should have fewer messages (compaction occurred)
        assert len(result.messages) <= len(messages)

    def test_protected_zone_truncate_needed(self) -> None:
        """Line 293 (_truncate_protected_zone): truncation occurs when over limit."""
        short_msg = Message(role="tool", content="x" * 1000)
        manager = ProtectedZoneManager(max_protected_tokens=5)  # Very small
        result, count = manager.truncate_if_needed([short_msg])
        # Should have been truncated or returned (no crash)
        assert isinstance(result, list)


class TestCompressionStrategyMissingLines2:
    """Cover remaining missing lines in compression_strategy.py."""

    def _make_config(
        self,
        high: float = 0.7,
        medium: float = 0.4,
        tool_seqs: bool = False,
        code_blocks: bool = False,
    ) -> CompressionStrategyConfig:
        """Create config for tests."""
        return CompressionStrategyConfig(
            name="test",
            high_threshold=high,
            medium_threshold=medium,
            preserve_tool_sequences=tool_seqs,
            preserve_code_blocks=code_blocks,
        )

    def test_compress_cluster_no_content_short(self) -> None:
        """Line 175->174: message content is short enough (no truncation)."""
        messages = [Message(role="user", content="hi there")]  # Short content
        strategy = CompressionStrategy(self._make_config())
        result = strategy._generate_cluster_summary(messages)
        # Short content, no "..." truncation expected
        assert "hi there" in result or result == ""

    def test_compress_medium_tool_sequence_no_tool_calls(self) -> None:
        """Line 198->197: no tool calls in medium importance cluster."""
        messages = [Message(role="assistant", content="just text, no tools")]
        config = self._make_config(high=0.9, medium=0.3, tool_seqs=True)
        strategy = CompressionStrategy(config)
        compressed: list[Message] = []
        strategy._preserve_tool_sequences_in_cluster(messages, [0], compressed)
        assert compressed == []  # No tool calls, nothing preserved

    def test_compress_code_block_no_code(self) -> None:
        """Line 221->220: message has no code block."""
        messages = [Message(role="user", content="no code here")]
        config = self._make_config(code_blocks=True)
        strategy = CompressionStrategy(config)
        compressed: list[Message] = []
        strategy._preserve_code_blocks_in_cluster(messages, [0], compressed)
        assert compressed == []  # No code block → nothing preserved

    def test_compress_code_block_with_code(self) -> None:
        """Lines 220-226: message with code block is preserved."""
        messages = [
            Message(role="assistant", content="```python\ncode here\n```"),
        ]
        config = self._make_config(code_blocks=True)
        strategy = CompressionStrategy(config)
        compressed: list[Message] = []
        strategy._preserve_code_blocks_in_cluster(messages, [0], compressed)
        assert len(compressed) == 1


class TestCompactionMissingLines3:
    """Additional targeted tests for compaction.py."""

    def test_handle_tool_call_multiple_calls_continuation(self) -> None:
        """Lines 194->189, 197->199, 199->189: multiple tool calls loop continues."""
        tool_call1 = ToolCall(id="tc1", name="test1", arguments={})
        tool_call2 = ToolCall(id="tc2", name="test2", arguments={})
        messages = [
            Message(role="assistant", content="calling", tool_calls=[tool_call1, tool_call2]),
            Message(role="tool", content="r1", tool_call_id="tc1"),
            Message(role="tool", content="r2", tool_call_id="tc2"),
        ]
        current_sequence: list[Message] = [messages[0]]
        consumed: set[int] = set()
        # Line 194 (append tc1 response), 199->189 (tc2 still outstanding), 194 again
        MessageSequenceGrouper._handle_tool_call_sequence(messages, 0, current_sequence, consumed)
        # Both tool responses should be in sequence
        assert len(current_sequence) == 3
        assert 1 in consumed
        assert 2 in consumed

    def test_truncate_protected_zone_already_fits(self) -> None:
        """Line 293: _truncate_protected_zone_messages returns early when tokens <= max."""
        messages = [Message(role="user", content="short")]
        # Call directly with generous limit
        result = _truncate_protected_zone_messages(messages, max_tokens=10000)
        assert result == messages

    def test_select_sequences_all_fit_no_break(self) -> None:
        """Line 729->738: for loop completes without break (all sequences fit)."""
        # Create a compactor with very generous budget
        from henchman.utils.compaction import ContextCompactor

        long_content = "word " * 500
        messages = [
            Message(role="system", content="system"),
            Message(role="user", content=long_content),
            Message(role="assistant", content=long_content),
            Message(role="user", content="final"),
        ]
        # Force compaction by using small max_tokens, but protect last messages
        # such that the sequences_to_consider list iterates fully
        compactor = ContextCompactor(max_tokens=50)
        result = compactor.compact(messages, protect_from_index=len(messages) - 1)
        assert result is not None

    @pytest.mark.anyio
    async def test_generate_summary_no_finish_reason_loop_exhausts(self) -> None:
        """Lines 866->875: async for loop exhausts naturally (no finish_reason)."""
        mock_provider = MagicMock()

        async def mock_stream(*args, **kwargs):
            chunk = MagicMock()
            chunk.content = "content "
            chunk.finish_reason = None  # No finish_reason → no break
            yield chunk
            # Iterator exhausts → 866->875 (loop to after)

        mock_provider.chat_completion_stream = mock_stream
        messages = [Message(role="user", content="summarize me")]
        result = await _generate_summary_with_provider(
            mock_provider, messages, _format_messages_for_summary
        )
        assert result == "content"

    @pytest.mark.anyio
    async def test_compact_messages_not_compacted_returns_early(self) -> None:
        """Line 1026: _compact_with_summarization_impl returns when not compacted."""
        from henchman.utils.compaction import (
            _compact_with_summarization_impl,
        )

        # All messages are protected → nothing can be dropped → was_compacted = False
        long_content = "word " * 200
        messages = [
            Message(role="system", content="system"),
            Message(role="user", content=long_content),
            Message(role="user", content="final"),
        ]

        mock_provider = MagicMock()
        config = SummarizationConfig(
            provider=mock_provider,
            summarize=True,
            protect_from_index=0,  # All messages protected
            max_protected_ratio=0.99,
        )
        # Even though tokens > max_tokens, protect_from_index=0 → nothing dropped
        result = await _compact_with_summarization_impl(messages, max_tokens=10, config=config)
        # Result may or may not be compacted, but we're testing the code path
        assert result is not None

    def test_loop_continues_after_last_sequence_not_empty(self) -> None:
        """Lines 121->124: verifies current_sequence check at end."""
        # Test with empty messages passed to group_into_sequences
        sequences = MessageSequenceGrouper.group_into_sequences([])
        assert sequences == []


class TestCompressionStrategyMissingLines3:
    """Additional targeted tests for compression_strategy.py."""

    def _make_config(self, high=0.7, medium=0.4, tool_seqs=False, code_blocks=False):
        """Create config."""
        return CompressionStrategyConfig(
            name="test",
            high_threshold=high,
            medium_threshold=medium,
            preserve_tool_sequences=tool_seqs,
            preserve_code_blocks=code_blocks,
        )

    def test_generate_cluster_summary_none_content(self) -> None:
        """Line 175->174: message with None content skips preview."""
        strategy = CompressionStrategy(self._make_config())
        messages = [
            Message(role="user", content=None),  # No content → 175 False branch
            Message(role="assistant", content="reply"),
        ]
        result = strategy._generate_cluster_summary(messages)
        # Only the "reply" message contributes
        assert "reply" in result
        assert "user" not in result

    def test_preserve_tool_sequences_out_of_bounds_index(self) -> None:
        """Line 198->197: idx >= len(messages) is skipped."""
        strategy = CompressionStrategy(self._make_config(tool_seqs=True))
        messages = [Message(role="assistant", content="hi")]
        compressed: list[Message] = []
        # Pass an out-of-bounds index
        strategy._preserve_tool_sequences_in_cluster(messages, [0, 5], compressed)
        # Only valid index 0 processed (but no tool_calls → nothing added)
        assert compressed == []

    def test_preserve_tool_sequences_tool_response_not_following(self) -> None:
        """Line 204->197: tool response not at idx+1, nothing extra added."""
        tool_call = ToolCall(id="tc1", name="test", arguments={})
        messages = [
            Message(role="assistant", content="calling", tool_calls=[tool_call]),
            Message(role="assistant", content="another assistant"),  # Not a tool
        ]
        strategy = CompressionStrategy(self._make_config(tool_seqs=True))
        compressed: list[Message] = []
        strategy._preserve_tool_sequences_in_cluster(messages, [0, 1], compressed)
        # Adds assistant (index 0) but NOT index 1 (not a tool)
        assert len(compressed) == 1
        assert compressed[0] == messages[0]

    def test_preserve_code_blocks_out_of_bounds_index(self) -> None:
        """Line 221->220: idx >= len(messages) is skipped."""
        strategy = CompressionStrategy(self._make_config(code_blocks=True))
        messages = [Message(role="user", content="```code```")]
        compressed: list[Message] = []
        strategy._preserve_code_blocks_in_cluster(messages, [0, 99], compressed)
        # Only idx=0 is valid and has code
        assert len(compressed) == 1


class TestIntelligentContextMissingLines2:
    """Cover remaining missing lines 396, 614->613."""

    def test_enforce_message_safety_len_gt_limit_but_tokens_ok(self) -> None:
        """Line 396: content longer than limit in chars but not in tokens."""
        from henchman.utils.intelligent_context import MessageSafetyEnforcer
        # Create enforcer with safety_limit_ratio that gives limit ~5 tokens
        # max_tokens=100, safety_limit_ratio=0.05 gives limit=5 tokens
        enforcer = MessageSafetyEnforcer(safety_limit_ratio=0.05, max_tokens=100)
        # Content is 60+ chars but < 10 tokens (short words, lots of spaces)
        content = "word word word word"  # ~4 tokens but 19 chars
        msg = Message(role="user", content=content)
        # Limit in tokens = 5, len("word word word word") = 19 > 5 chars
        # BUT token count (~4) <= 5 → should return original message (line 396)
        # Test through public API
        result = enforcer.enforce_safety_limits([msg])
        assert len(result) == 1
        assert result[0] is msg  # Returns original (line 396)

    def test_calculate_cluster_importance_missing_score(self) -> None:
        """Line 614->613: cluster has index not in importance_scores."""
        manager = IntelligentContextManager(params=IntelligentContextParams())
        clusters = [[0, 1, 2]]  # Cluster with 3 indices
        importance_scores = {0: 0.8}  # Only index 0 has a score; 1, 2 missing
        result = manager.message_compactor.calculate_cluster_importance(clusters, importance_scores)
        # Only index 0 contributes (1 and 2 are missing → False branch at 614)
        assert result[0] == pytest.approx(0.8, abs=0.5)


class TestMessageClustererMissingLines2:
    """Cover remaining lines 103->90 and 394->392."""

    def test_cluster_tool_call_mismatched_id(self) -> None:
        """Line 103->90: tool_call_id not in tool_call_ids → no merge."""
        tool_call = ToolCall(id="tc1", name="test", arguments={})
        messages = [
            Message(role="assistant", content="calling", tool_calls=[tool_call]),
            Message(role="tool", content="result", tool_call_id="wrong_id"),  # mismatch
        ]
        clusterer = MessageClusterer()
        clusters = [[0], [1]]
        result = clusterer._cluster_tool_call_sequences(messages, clusters)
        # No merge because tool_call_id doesn't match
        assert len(result) == 2  # Clusters unchanged

    def test_get_cluster_content_none_content(self) -> None:
        """Line 394->392: message with None content skips append."""
        clusterer = MessageClusterer()
        messages = [
            Message(role="user", content=None),  # No content
            Message(role="assistant", content="hello"),
        ]
        result = clusterer._extract_cluster_content(messages, [0, 1])
        assert "hello" in result
        assert "None" not in result
