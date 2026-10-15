"""RED→GREEN test: Rich markup should render correctly in trusted system messages.

Bug: [bold]Henchman-AI[/bold] appears literally instead of rendering as bold.
Root cause: ChatMessage._render_plain_text() escapes ALL markup via _safe_markup().
Fix: Add `trusted` flag so system messages render markup, user content is escaped.
"""

from rich.console import Console
from rich.text import Text

from henchman.cli.textual_widgets import ChatMessage, ChatPane


class TestSystemMessageRichMarkup:
    """System messages should render Rich markup tags, not display them literally."""

    def test_welcome_message_renders_bold(self):
        """[bold]Henchman-AI[/bold] should produce bold text, not literal tags."""
        msg = ChatMessage(
            prefix="[dim]\u00bb[/]",
            content="[bold]Henchman-AI[/bold] | deepseek:chat | 34 tools",
            trusted=True,
        )
        rendered = str(msg.renderable)
        assert "Henchman-AI" in rendered
        # The markup string should NOT have escaped backslashes
        assert "\\[bold\\]" not in rendered, (
            f"Escaped backslashes found in trusted output: {rendered!r}"
        )
        # Verify the semantic style without depending on terminal colour settings.
        parsed = Text.from_markup(rendered)
        offset = parsed.plain.index("Henchman-AI")
        assert parsed.get_style_at_offset(Console(), offset).bold is True

    def test_system_message_with_colored_markup(self):
        """Markup like [cyan]text[/] should render, not appear literally."""
        msg = ChatMessage(
            prefix="[dim]\u00bb[/]",
            content="Provider switched: [cyan]old[/] -> [cyan]new[/]",
            trusted=True,
        )
        rendered = str(msg.renderable)
        assert "\\[cyan\\]" not in rendered, (
            f"Escaped backslashes found in trusted output: {rendered!r}"
        )
        parsed = Text.from_markup(rendered)
        assert "old" in parsed.plain and "new" in parsed.plain
        console = Console()
        for token in ("old", "new"):
            offset = parsed.plain.index(token)
            color = parsed.get_style_at_offset(console, offset).color
            assert color is not None
            assert color.name == "cyan"

    def test_chatpane_add_system_message_renders_markup(self):
        """Messages added via add_system_message should render Rich markup."""
        pane = ChatPane()
        pane.add_system_message("[bold blue]Henchman-AI[/] - /help for commands")
        assert len(pane.children) == 1
        msg_widget = pane.children[0]
        rendered = str(msg_widget.renderable)
        assert "Henchman-AI" in rendered
        assert "\\[bold blue\\]" not in rendered, (
            f"Escaped backslashes in ChatPane system message: {rendered!r}"
        )

    def test_user_message_still_escapes_untrusted_content(self):
        """User-supplied content must still be escaped to prevent injection."""
        user_input = "Please run [rm -rf /] on the server"
        msg = ChatMessage(
            prefix="[bold green]You:[/]",
            content=user_input,
        )
        rendered = str(msg.renderable)
        assert "rm -rf" in rendered
        # User content should have backslash-escaped brackets
        assert "\\[rm -rf" in rendered, (
            f"User content was not escaped: {rendered!r}"
        )

    def test_default_trusted_is_false(self):
        """ChatMessage without trusted=True should escape markup by default."""
        msg = ChatMessage(
            prefix="[dim]»[/]",
            content="[bold]test[/bold]",
        )
        rendered = str(msg.renderable)
        # markup_escape escapes '[' to '\[' but doesn't escape ']'
        # So we check for '\[' before 'bold' and '\[' before '/bold'
        assert "\\[bold]" in rendered, (
            f"Default (untrusted) should escape opening tag: {rendered!r}"
        )
        assert "\\[/bold]" in rendered, (
            f"Default (untrusted) should escape closing tag: {rendered!r}"
        )
