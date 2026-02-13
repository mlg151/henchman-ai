"""Tests for tiktoken integration in TokenCounter."""

from henchman.providers.base import Message, ToolCall
from henchman.utils.tokens import (
    DEFAULT_MODEL_LIMIT,
    MODEL_LIMITS,
    TokenCounter,
    get_model_limit,
)


class TestModelLimits:
    """Tests for model limit configuration."""

    def test_model_limits_dict_exists(self):
        """MODEL_LIMITS should be a non-empty dict."""
        assert isinstance(MODEL_LIMITS, dict)
        assert len(MODEL_LIMITS) > 0

    def test_deepseek_limit(self):
        """DeepSeek models should have 128K limit."""
        assert MODEL_LIMITS["deepseek-chat"] == 128000
        assert MODEL_LIMITS["deepseek-reasoner"] == 128000

    def test_claude_limit(self):
        """Claude models should have 200K limit."""
        assert MODEL_LIMITS["claude-sonnet-4-20250514"] == 200000
        assert MODEL_LIMITS["claude-3-opus-20240229"] == 200000

    def test_gpt4_limit(self):
        """GPT-4 models should have appropriate limits."""
        assert MODEL_LIMITS["gpt-4-turbo"] == 128000
        assert MODEL_LIMITS["gpt-4"] == 8192

    def test_get_model_limit_known_model(self):
        """get_model_limit returns correct limit for known models."""
        assert get_model_limit("deepseek-chat") == 128000
        assert get_model_limit("gpt-4") == 8192

    def test_get_model_limit_unknown_model(self):
        """get_model_limit returns default for unknown models."""
        assert get_model_limit("unknown-model") == DEFAULT_MODEL_LIMIT
        assert get_model_limit("") == DEFAULT_MODEL_LIMIT


class TestTiktokenTokenCounter:
    """Tests for tiktoken-based token counting."""

    def test_count_text_empty(self):
        """Empty text should return 0 tokens."""
        assert TokenCounter.count_text("") == 0

    def test_count_text_simple(self):
        """Simple text should return reasonable token count."""
        # "Hello, world!" is typically 4 tokens in cl100k_base
        tokens = TokenCounter.count_text("Hello, world!")
        assert tokens > 0
        assert tokens < 10

    def test_count_text_long(self):
        """Long text should return proportionally more tokens."""
        short = TokenCounter.count_text("Hello")
        long_text = "Hello " * 100
        long_tokens = TokenCounter.count_text(long_text)
        assert long_tokens > short * 50  # Should scale roughly

    def test_count_text_with_model(self):
        """Token count with model parameter should work."""
        text = "Hello, world!"
        # Both should work, may or may not give same result
        default_tokens = TokenCounter.count_text(text)
        gpt4_tokens = TokenCounter.count_text(text, model="gpt-4")
        assert default_tokens > 0
        assert gpt4_tokens > 0

    def test_count_text_with_unknown_model(self):
        """Unknown model should fall back to default encoding."""
        text = "Hello, world!"
        tokens = TokenCounter.count_text(text, model="unknown-model-xyz")
        assert tokens > 0

    def test_count_messages_empty(self):
        """Empty message list should return minimal tokens."""
        tokens = TokenCounter.count_messages([])
        # Still has base overhead
        assert tokens >= 0

    def test_count_messages_simple(self):
        """Single message should include overhead."""
        msg = Message(role="user", content="Hello")
        tokens = TokenCounter.count_messages([msg])
        content_tokens = TokenCounter.count_text("Hello")
        # Should be more than just content due to overhead
        assert tokens > content_tokens

    def test_count_messages_with_tool_calls(self):
        """Messages with tool calls should count tool overhead."""
        tc = ToolCall(id="tc-1", name="read_file", arguments={"path": "/etc/hosts"})
        msg = Message(role="assistant", content="I'll read the file.", tool_calls=[tc])

        tokens_with_tools = TokenCounter.count_messages([msg])

        # Without tool calls
        msg_no_tools = Message(role="assistant", content="I'll read the file.")
        tokens_without_tools = TokenCounter.count_messages([msg_no_tools])

        # Should be more with tool calls
        assert tokens_with_tools > tokens_without_tools

    def test_count_messages_with_tool_result(self):
        """Tool result messages should count tool_call_id."""
        msg = Message(role="tool", content="File contents here", tool_call_id="tc-1")
        tokens = TokenCounter.count_messages([msg])
        assert tokens > 0

    def test_encoding_caching(self):
        """Encodings should be cached for performance."""
        # Access encoding twice
        TokenCounter.count_text("test1")
        TokenCounter.count_text("test2")

        # Should have cached encoding
        assert "cl100k_base" in TokenCounter._encodings

    def test_count_messages_conversation(self):
        """Full conversation should sum properly."""
        msgs = [
            Message(role="system", content="You are helpful."),
            Message(role="user", content="What is 2+2?"),
            Message(role="assistant", content="2+2 equals 4."),
        ]
        tokens = TokenCounter.count_messages(msgs)

        # Should be sum of individual messages plus overhead
        individual_sum = sum(TokenCounter.count_messages([m]) for m in msgs)
        # Total should be close to sum (may differ due to base overhead)
        assert abs(tokens - individual_sum) < 20


class TestTokenCounterEdgeCases:
    """Edge case tests for TokenCounter."""

    def test_unicode_text(self):
        """Unicode text should be counted correctly."""
        # Emoji and non-ASCII chars
        text = "Hello 🌍! Привет мир! 你好世界!"
        tokens = TokenCounter.count_text(text)
        assert tokens > 0

    def test_code_snippet(self):
        """Code snippets should be tokenized."""
        code = """
def hello():
    print("Hello, world!")
    return 42
"""
        tokens = TokenCounter.count_text(code)
        assert tokens > 10  # Code has multiple tokens

    def test_json_content(self):
        """JSON content should be tokenized."""
        import json

        data = {"key": "value", "nested": {"a": 1, "b": 2}}
        json_str = json.dumps(data)
        tokens = TokenCounter.count_text(json_str)
        assert tokens > 0

    def test_very_long_text(self):
        """Very long text should not cause issues."""
        # 100KB of text
        long_text = "word " * 20000
        tokens = TokenCounter.count_text(long_text)
        assert tokens > 10000  # Should be many tokens

    def test_message_with_none_content(self):
        """Message with None content should be handled."""
        msg = Message(
            role="assistant", content=None, tool_calls=[ToolCall(id="1", name="test", arguments={})]
        )
        tokens = TokenCounter.count_messages([msg])
        assert tokens > 0  # Should count tool calls at least
