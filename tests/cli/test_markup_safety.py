"""Tests for Rich markup safety — no unescaped content should crash widgets.

Every path that passes user/tool/agent content to a Rich-markup-enabled
widget (.update(), .write()) must strip ANSI codes and escape Rich tags.
"""

import pytest
from rich.markup import escape as markup_escape


# ---------------------------------------------------------------------------
# Payloads that previously caused MarkupError crashes
# ---------------------------------------------------------------------------

ANSI_PAYLOADS = [
    # CI pipeline output with ANSI colour codes
    "✗ \x1b[1;33m=== CI Pipeline ===\x1b[0m\n\x1b[1;33m[1/5] Running ruff\x1b[0m",
    # git diff with colour
    "\x1b[32m+added line\x1b[0m\n\x1b[31m-removed line\x1b[0m",
    # pytest output
    "\x1b[1m===== 5 passed =====\x1b[0m",
    # nested ANSI
    "\x1b[1;31;40mERROR\x1b[0m: Something [broke]",
]

RICH_MARKUP_PAYLOADS = [
    # Square brackets in normal text
    "array[0] = value",
    "config[key] is missing",
    # Rich-like tags that aren't valid
    "[notacolor]text[/notacolor]",
    "[bold red on blue]crash me[/]",
    # Unterminated tags
    "[bold without close",
    "text with ] only",
]

MIXED_PAYLOADS = [
    # ANSI + Rich-like content
    "\x1b[33m[WARNING]\x1b[0m Something [failed]",
    # Tool output with both
    "Result: \x1b[1;33m=== Henchman-AI CI Pipeline ===\x1b[0m\n\n"
    "\x1b[1;33m[1/5] Running ruff linter...\x1b[0m",
]

ALL_PAYLOADS = ANSI_PAYLOADS + RICH_MARKUP_PAYLOADS + MIXED_PAYLOADS


# ---------------------------------------------------------------------------
# Unit tests for _safe_markup helper
# ---------------------------------------------------------------------------


class TestSafeMarkup:
    """The _safe_markup helper must strip ANSI and escape Rich tags."""

    def test_import(self):
        """_safe_markup is importable from textual_widgets."""
        from henchman.cli.textual_widgets import _safe_markup

        assert callable(_safe_markup)

    @pytest.mark.parametrize("payload", ANSI_PAYLOADS, ids=range(len(ANSI_PAYLOADS)))
    def test_strips_ansi_codes(self, payload):
        """ANSI escape sequences must be removed."""
        from henchman.cli.textual_widgets import _safe_markup

        result = _safe_markup(payload)
        assert "\x1b" not in result
        assert "\033" not in result

    @pytest.mark.parametrize(
        "payload", RICH_MARKUP_PAYLOADS, ids=range(len(RICH_MARKUP_PAYLOADS))
    )
    def test_escapes_rich_tags(self, payload):
        """Rich markup brackets must be escaped or neutralised."""
        from henchman.cli.textual_widgets import _safe_markup

        result = _safe_markup(payload)
        # The real contract: Rich/Textual must not choke on the result
        from textual.visual import visualize

        visualize(None, result, markup=True)  # must not raise

    @pytest.mark.parametrize("payload", ALL_PAYLOADS, ids=range(len(ALL_PAYLOADS)))
    def test_no_markup_error_from_rich(self, payload):
        """Escaped text must not raise MarkupError when rendered by Rich."""
        from io import StringIO

        from rich.console import Console

        from henchman.cli.textual_widgets import _safe_markup

        safe = _safe_markup(payload)
        console = Console(file=StringIO(), force_terminal=True)
        # This must not raise MarkupError
        console.print(f"[dim]{safe}[/]")

    @pytest.mark.parametrize("payload", ALL_PAYLOADS, ids=range(len(ALL_PAYLOADS)))
    def test_no_markup_error_from_textual_visualize(self, payload):
        """Escaped text must not raise MarkupError in Textual visualize."""
        from textual.visual import visualize

        from henchman.cli.textual_widgets import _safe_markup

        safe = _safe_markup(payload)
        # This is the exact code path that crashed in production
        visualize(None, f"[dim]{safe}[/]", markup=True)

    def test_exact_crash_payload(self):
        """Reproduce the exact payload from the bug report."""
        from textual.visual import visualize

        from henchman.cli.textual_widgets import _safe_markup

        crash_payload = (
            "✗ \x1b[1;33m=== Henchman-AI CI Pipeline ===\x1b[0m\n\n"
            "\x1b[1;33m[1/5] Running ruff linter...\x1b[0m"
        )
        safe = _safe_markup(f"Result: {crash_payload}")
        # Both of the production code paths that crashed:
        visualize(None, f"🛠️ {safe}", markup=True)
        visualize(None, f"[green]← {safe}[/]", markup=True)

    def test_preserves_readable_content(self):
        """Readable text content is preserved after stripping ANSI."""
        from henchman.cli.textual_widgets import _safe_markup

        result = _safe_markup("\x1b[33mHello World\x1b[0m")
        assert "Hello World" in result

    def test_empty_string(self):
        """Empty input returns empty output."""
        from henchman.cli.textual_widgets import _safe_markup

        assert _safe_markup("") == ""

    def test_none_returns_empty(self):
        """None input returns empty string."""
        from henchman.cli.textual_widgets import _safe_markup

        assert _safe_markup(None) == ""  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Widget integration tests — widgets must not crash on bad input
# ---------------------------------------------------------------------------


class TestToolMessageMarkupSafety:
    """ToolMessage must not crash on ANSI/Rich-tag content."""

    @pytest.mark.parametrize("payload", ALL_PAYLOADS, ids=range(len(ALL_PAYLOADS)))
    def test_init_with_dangerous_thought(self, payload):
        """ToolMessage(thought=<dangerous>) must not raise."""
        from henchman.cli.textual_widgets import ToolMessage

        msg = ToolMessage(thought=payload)
        # Must not crash
        str(msg.render())

    @pytest.mark.parametrize("payload", ALL_PAYLOADS, ids=range(len(ALL_PAYLOADS)))
    def test_append_dangerous_content(self, payload):
        """ToolMessage.append(<dangerous>) must not raise."""
        from henchman.cli.textual_widgets import ToolMessage

        msg = ToolMessage(thought="safe")
        msg.append(payload)
        str(msg.render())

    @pytest.mark.parametrize("payload", ALL_PAYLOADS, ids=range(len(ALL_PAYLOADS)))
    def test_set_content_dangerous(self, payload):
        """ToolMessage.set_content(<dangerous>) must not raise."""
        from henchman.cli.textual_widgets import ToolMessage

        msg = ToolMessage(thought="safe")
        msg.set_content(payload)
        str(msg.render())


class TestThinkingMessageMarkupSafety:
    """ThinkingMessage must not crash on ANSI/Rich-tag content."""

    @pytest.mark.parametrize("payload", ALL_PAYLOADS, ids=range(len(ALL_PAYLOADS)))
    def test_init_with_dangerous_thought(self, payload):
        """ThinkingMessage(thought=<dangerous>) must not raise."""
        from henchman.cli.textual_widgets import ThinkingMessage

        msg = ThinkingMessage(thought=payload)
        str(msg.render())

    @pytest.mark.parametrize("payload", ALL_PAYLOADS, ids=range(len(ALL_PAYLOADS)))
    def test_append_dangerous_content(self, payload):
        """ThinkingMessage.append(<dangerous>) must not raise."""
        from henchman.cli.textual_widgets import ThinkingMessage

        msg = ThinkingMessage(thought="safe")
        msg.append(payload)
        str(msg.render())


class TestChatMessageMarkupSafety:
    """ChatMessage must not crash on ANSI/Rich-tag content."""

    @pytest.mark.parametrize("payload", ALL_PAYLOADS, ids=range(len(ALL_PAYLOADS)))
    def test_init_with_dangerous_content(self, payload):
        """ChatMessage(<dangerous>) must not raise."""
        from henchman.cli.textual_widgets import ChatMessage

        msg = ChatMessage("[bold]Agent:[/]", payload)
        str(msg.render())

    @pytest.mark.parametrize("payload", ALL_PAYLOADS, ids=range(len(ALL_PAYLOADS)))
    def test_append_dangerous_content(self, payload):
        """ChatMessage.append(<dangerous>) must not raise."""
        from henchman.cli.textual_widgets import ChatMessage

        msg = ChatMessage("[bold]Agent:[/]", "safe")
        msg.append(payload)
        str(msg.render())


class TestChatPaneMarkupSafety:
    """ChatPane methods must not crash on dangerous content."""

    @pytest.mark.parametrize("payload", ALL_PAYLOADS, ids=range(len(ALL_PAYLOADS)))
    def test_add_tool_message_dangerous(self, payload):
        """ChatPane.add_tool_message(<dangerous>) must not raise."""
        from henchman.cli.textual_widgets import ChatPane

        pane = ChatPane()
        pane.add_tool_message(payload)

    @pytest.mark.parametrize("payload", ALL_PAYLOADS, ids=range(len(ALL_PAYLOADS)))
    def test_add_thinking_message_dangerous(self, payload):
        """ChatPane.add_thinking_message(<dangerous>) must not raise."""
        from henchman.cli.textual_widgets import ChatPane

        pane = ChatPane()
        pane.add_thinking_message(payload)
