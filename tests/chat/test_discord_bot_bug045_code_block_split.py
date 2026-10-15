"""Test for BUG-045: Code block closing fence at chunk boundary produces malformed Markdown.

When a code block's closing fence (```) triggers a chunk split, `code_block_lang`
is still set to the language name, so the new chunk incorrectly opens with
` ```python\n ``` ` instead of just ` ``` `.

The fix: use `next_lang` when opening a new chunk during a split to correctly
handle closing fences.
"""

from __future__ import annotations


class TestCodeBlockSplit:
    """Tests for _split_message code block handling."""

    def test_closing_fence_at_boundary_no_reopening(self) -> None:
        """Closing fence at chunk boundary must not re-open the code block."""
        from henchman.chat.discord_bot import DiscordBot

        # Build content where the closing fence comes near the chunk limit
        content = "```python\n"
        content += "# Some code\n"
        content += "# " + ("x" * (1980 - len("# Some code\n# ")))
        content += "\n```\nNormal text after the block"
        assert len(content) > 2000

        chunks = DiscordBot._split_message(content, 2000)

        for chunk in chunks:
            assert "```python\n```" not in chunk, (
                f"Found malformed code block reopening in chunk: {chunk[:50]}..."
            )

    def test_closing_fence_respects_language(self) -> None:
        """Code block language must still be tracked correctly after split."""
        from henchman.chat.discord_bot import DiscordBot

        content = (
            "Here's some code:\n"
            "```python\n"
            "def hello():\n"
            "    print('Hello')\n"
            "```\n"
            "That's all."
        )
        chunks = DiscordBot._split_message(content, 50)

        for chunk in chunks:
            assert len(chunk) <= 50

        for chunk in chunks:
            assert "```python\n```" not in chunk, (
                f"Found malformed code block reopening in chunk: {chunk[:60]}..."
            )

    def test_consecutive_code_blocks(self) -> None:
        """Multiple code blocks in a message should split correctly."""
        from henchman.chat.discord_bot import DiscordBot

        content = (
            "```python\n"
            "def f():\n"
            "    pass\n"
            "```\n"
            "```java\n"
            "class Foo {}\n"
            "```"
        )
        chunks = DiscordBot._split_message(content, 60)

        for chunk in chunks:
            assert len(chunk) <= 60

        for chunk in chunks:
            assert "```python\n```" not in chunk
            assert "```java\n```" not in chunk

    def test_close_at_exact_boundary(self) -> None:
        """Closing fence at chunk boundary with language must not produce malformed output.

        The bug: when a code block closing fence `` ``` `` triggers a split,
        ``code_block_lang`` is still set (e.g. "python"), so the new chunk
        incorrectly opens with `` ```python\n ``` ``.

        The fix: use ``next_lang`` (which is None for a closing fence) to
        decide whether to open a new code block in the new chunk.
        """
        from henchman.chat.discord_bot import DiscordBot

        # Build content where the closing fence line itself triggers the split.
        # Fill a code block to within 5 chars of the limit so the closing fence
        # (```) pushes it over.
        close_overhead = 4  # "\n```"
        code_open = "```python\n"  # 10 chars
        body_size = 2000 - len(code_open) - close_overhead + 1  # Just over limit
        body = "x" * (body_size - 1)  # minus 1 for the trailing newline before closing fence
        content = code_open + body + "\n```\nAfter block"
        assert len(content) > 2000, f"Content length {len(content)} should be > 2000"

        chunks = DiscordBot._split_message(content, 2000)

        for chunk in chunks:
            assert "```python\n```" not in chunk, (
                f"Found malformed code block reopening in chunk: {repr(chunk[:60])}..."
            )
