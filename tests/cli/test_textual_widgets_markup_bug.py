"""RED test: Rich markup should render correctly in trusted system messages.

Bug: [bold]Henchman-AI[/bold] appears literally instead of rendering as bold.
Root cause: ChatMessage._render_plain_text() escapes ALL markup via _safe_markup().
"""

import pytest

from henchman.cli.textual_widgets import ChatMessage, ChatPane


class TestSystemMessageRichMarkup:
    """System messages should render Rich markup tags, not display them literally."""

    def test_welcome_message_renders_bold(self):
        """[bold]Henchman-AI[/bold] should produce bold text, not literal tags."""
        msg = ChatMessage(
            prefix="[dim]\u00bb[/]",
            content="[bold]Henchman-AI[/bold] | deepseek:chat | 34 tools",
        )
        rendered = str(msg.renderable)
        # The rendered text should contain the literal word "Henchman-AI"
        assert "Henchman-AI" in rendered
        # But should NOT contain the raw markup tags
        assert "[bold]" not in rendered, (
            f"Raw [bold] tag found in rendered output: {rendered!r}"
        )
        assert "[/bold]" not in rendered, (
            f"Raw [/bold] tag found in rendered output: {rendered!r}"
        )

    def test_system_message_with_colored_markup(self):
        """Markup like [cyan]text[/] should render, not appear literally."""
        msg = ChatMessage(
            prefix="[dim]\u00bb[/]",
            content="Provider switched: [cyan]old[/] -> [cyan]new[/]",
        )
        rendered = str(msg.renderable)
        assert "[cyan]" not in rendered, (
            f"Raw [cyan] tag found: {rendered!r}"
        )

    def test_chatpane_add_system_message_renders_markup(self):
        """Messages added via add_system_message should render Rich markup."""
        pane = ChatPane()
        pane.add_system_message("[bold blue]Henchman-AI[/] - /help for commands")
        assert len(pane.children) == 1
        msg_widget = pane.children[0]
        rendered = str(msg_widget.renderable)
        assert "Henchman-AI" in rendered
        assert "[bold blue]" not in rendered, (
            f"Raw markup in ChatPane system message: {rendered!r}"
        )

    def test_user_message_still_escapes_untrusted_content(self):
        """User-supplied content must still be escaped to prevent injection."""
        # Simulate user content with markup-like text
        user_input = "Please run [rm -rf /] on the server"
        msg = ChatMessage(
            prefix="[bold green]You:[/]",
            content=user_input,
        )
        rendered = str(msg.renderable)
        # The literal bracket text should be preserved (escaped)
        assert "rm -rf" in rendered
