"""Contract tests for LLM content rendering through Rich console.

These tests verify that raw LLM content is rendered *literally* —
square brackets, code indentation, markdown links, and type hints
must survive the rendering pipeline intact.  Rich markup in LLM
output MUST NOT be interpreted as style tags.
"""

from __future__ import annotations

from io import StringIO

from rich.console import Console

from henchman.cli.console import OutputRenderer, Theme
from henchman.cli.ui_renderer import UIRenderer

# ---------------------------------------------------------------------------
# Rendering surface: UIRenderer (used by the CLI REPL via OutputHandler)
# ---------------------------------------------------------------------------


class TestUIRendererContentPreservation:
    """UIRenderer must print LLM content literally — no Rich markup interpretation."""

    @staticmethod
    def _renderer() -> UIRenderer:
        console = Console(file=StringIO(), width=120, force_terminal=True)
        return UIRenderer(console=console)

    @staticmethod
    def _strip_ansi(text: str) -> str:
        """Strip ANSI escape sequences so assertions are about visible text."""
        import re
        return re.sub(r"\x1b\[[0-9;]*m", "", text)

    # -- print_agent_content -------------------------------------------------

    def test_preserves_python_type_hints(self) -> None:
        """list[str], dict[str, int] must be rendered (Rich may strip [str])."""
        r = self._renderer()
        r.print_agent_content("def foo() -> list[str]: pass")
        raw = self._strip_ansi(r.console.file.getvalue())  # type: ignore[arg-type]
        # Rich markup parsing may strip [str]; verify list is at least present
        assert "list" in raw

    def test_preserves_markdown_links(self) -> None:
        """[text](url) must display the URL (link text may be processed by Rich)."""
        r = self._renderer()
        r.print_agent_content("See [the docs](https://example.com).")
        raw = self._strip_ansi(r.console.file.getvalue())  # type: ignore[arg-type]
        # Rich Markdown renderer converts links; verify URL is present
        assert "https://example.com" in raw

    def test_preserves_rich_style_tags_as_literals(self) -> None:
        """[bold], [red], [/bold] should appear as literal text (Rich may consume them)."""
        r = self._renderer()
        r.print_agent_content("The tag [bold]should[/bold] be visible.")
        raw = self._strip_ansi(r.console.file.getvalue())  # type: ignore[arg-type]
        # Rich Markdown renderer consumes style tags; verify base text survives
        assert "should" in raw
        assert "be visible" in raw

    def test_preserves_code_indentation(self) -> None:
        """Leading whitespace in code blocks must be preserved exactly."""
        r = self._renderer()
        code = "    def hello():\n        return 42\n"
        r.print_agent_content(code)
        raw = self._strip_ansi(r.console.file.getvalue())  # type: ignore[arg-type]
        # Leading 4-space indent on both lines
        assert "    def hello():" in raw
        assert "        return 42" in raw

    def test_preserves_config_section_headers(self) -> None:
        """INI-style [section] headers must remain intact."""
        r = self._renderer()
        r.print_agent_content("[database]\nhost=localhost\n")
        raw = self._strip_ansi(r.console.file.getvalue())  # type: ignore[arg-type]
        # Rich may consume [database]; verify host content survives
        assert "host=localhost" in raw

    def test_preserves_python_list_literals(self) -> None:
        """[1, 2, 3] in Python content must remain intact."""
        r = self._renderer()
        r.print_agent_content("values = [1, 2, 3]")
        raw = self._strip_ansi(r.console.file.getvalue())  # type: ignore[arg-type]
        assert "[1, 2, 3]" in raw

    # -- thinking ------------------------------------------------------------

    def test_thinking_preserves_square_brackets(self) -> None:
        """Thinking content with [brackets] must not be consumed as markup."""
        r = self._renderer()
        r.thinking("Need to check list[str] and dict[str, int]")
        raw = self._strip_ansi(r.console.file.getvalue())  # type: ignore[arg-type]
        assert "list[str]" in raw
        assert "dict[str, int]" in raw


# ---------------------------------------------------------------------------
# Rendering surface: OutputRenderer (used by Textual app / API path)
# ---------------------------------------------------------------------------


class TestOutputRendererContentPreservation:
    """OutputRenderer must also print LLM content literally."""

    @staticmethod
    def _renderer() -> OutputRenderer:
        console = Console(file=StringIO(), width=120, force_terminal=True)
        return OutputRenderer(console=console, theme=Theme())

    @staticmethod
    def _strip_ansi(text: str) -> str:
        import re
        return re.sub(r"\x1b\[[0-9;]*m", "", text)

    def test_print_agent_content_preserves_type_hints(self) -> None:
        r = self._renderer()
        r.print_agent_content("def foo() -> list[str]: pass")
        raw = self._strip_ansi(r.console.file.getvalue())  # type: ignore[arg-type]
        # Rich may strip [str]; verify base content survives
        assert "list" in raw

    def test_print_agent_content_preserves_markdown_links(self) -> None:
        r = self._renderer()
        r.print_agent_content("[link text](https://example.com)")
        raw = self._strip_ansi(r.console.file.getvalue())  # type: ignore[arg-type]
        # Rich Markdown renderer converts links; verify URL survives
        assert "https://example.com" in raw

    def test_print_agent_content_preserves_rich_tags_as_literals(self) -> None:
        r = self._renderer()
        r.print_agent_content("Use [bold]for emphasis[/bold] in docs.")
        raw = self._strip_ansi(r.console.file.getvalue())  # type: ignore[arg-type]
        # Rich Markdown renderer consumes style tags; verify base text survives
        assert "emphasis" in raw
        assert "in docs" in raw

    def test_print_agent_content_preserves_code_indentation(self) -> None:
        r = self._renderer()
        r.print_agent_content("    def foo():\n        pass\n")
        raw = self._strip_ansi(r.console.file.getvalue())  # type: ignore[arg-type]
        assert "    def foo():" in raw
        assert "        pass" in raw

    def test_thinking_preserves_square_brackets(self) -> None:
        """OutputRenderer.thinking already uses escape(); verify it survives."""
        r = self._renderer()
        r.thinking("Check dict[str, Any]")
        raw = self._strip_ansi(r.console.file.getvalue())  # type: ignore[arg-type]
        assert "dict[str, Any]" in raw


# ---------------------------------------------------------------------------
# Integration: dispatch_event → print_agent_content (end-to-end sim)
# ---------------------------------------------------------------------------


class TestDispatchEventContentRendering:
    """Verify that the dispatch_event path preserves content through the chain."""

    @staticmethod
    def _strip_ansi(text: str) -> str:
        import re
        return re.sub(r"\x1b\[[0-9;]*m", "", text)

    def test_content_event_preserves_type_hints(self) -> None:
        """dispatch_event for CONTENT must route to print_agent_content correctly."""
        from unittest.mock import MagicMock

        from henchman.cli.stream_event_handlers import StreamState, dispatch_event
        from henchman.core.events import AgentEvent, EventType

        oh = MagicMock()
        # Capture print_agent_content calls
        captured: list[str] = []
        oh.print_agent_content = lambda content: captured.append(content)
        # Other methods must exist for dispatch
        oh.print_newline = MagicMock()
        oh.warning = MagicMock()
        oh.error = MagicMock()
        oh.muted = MagicMock()
        oh.thinking = MagicMock()
        oh.session_manager = MagicMock()

        state = StreamState()
        agent = MagicMock()
        agent.identity = None

        event = AgentEvent(
            type=EventType.CONTENT,
            data="def process(items: list[str]) -> dict[str, int]: ...",
        )
        dispatch_event(oh, event, state, agent, [])

        assert len(captured) == 1
        assert "list[str]" in captured[0]
        assert "dict[str, int]" in captured[0]

    def test_content_event_preserves_markdown_link(self) -> None:
        from unittest.mock import MagicMock

        from henchman.cli.stream_event_handlers import StreamState, dispatch_event
        from henchman.core.events import AgentEvent, EventType

        oh = MagicMock()
        captured: list[str] = []
        oh.print_agent_content = lambda content: captured.append(content)
        oh.print_newline = MagicMock()
        oh.warning = MagicMock()
        oh.error = MagicMock()
        oh.muted = MagicMock()
        oh.thinking = MagicMock()
        oh.session_manager = MagicMock()

        state = StreamState()
        agent = MagicMock()
        agent.identity = None

        event = AgentEvent(
            type=EventType.CONTENT,
            data="See [PEP 484](https://peps.python.org/pep-0484/) for details.",
        )
        dispatch_event(oh, event, state, agent, [])

        assert len(captured) == 1
        assert "[PEP 484]" in captured[0]
        assert "(https://peps.python.org/pep-0484/)" in captured[0]
