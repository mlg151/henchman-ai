"""Modal screens for the Henchman-AI Textual TUI.

Includes tool-confirmation, help/keybinding, and provider-selection
modals.

Note: Extracted from ``textual_app.py`` to keep modules under 500 lines.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label, Select

from henchman.cli.textual_messages import SwitchProviderMessage

if TYPE_CHECKING:
    from henchman.cli.textual_app import HenchmanTextualApp
    from henchman.tools.base import ConfirmationRequest

# Map risk level to Rich colour for the confirmation dialog.
_RISK_COLOURS: dict[str, str] = {
    "low": "green",
    "medium": "yellow",
    "high": "red",
}
_DEFAULT_RISK_COLOUR = "yellow"

# Provider names scanned when building the selector list.
_KNOWN_PROVIDERS = (
    "deepseek",
    "anthropic",
    "ollama",
    "openai",
)


# ------------------------------------------------------------------ #
# Tool confirmation                                                    #
# ------------------------------------------------------------------ #


class ConfirmToolScreen(ModalScreen[bool]):
    """Modal dialog for tool execution confirmation.

    Returns ``True`` if the user approves, ``False`` otherwise.
    """

    DEFAULT_CSS = """
    ConfirmToolScreen {
        align: center middle;
    }
    #confirm-dialog {
        padding: 2;
        border: solid $warning;
        background: $surface;
        width: 70;
        height: auto;
        max-height: 20;
    }
    #confirm-title {
        text-style: bold;
        margin-bottom: 1;
    }
    #confirm-details {
        margin-bottom: 1;
        color: $text-muted;
    }
    #confirm-buttons {
        align: right middle;
        height: auto;
        margin-top: 1;
    }
    """

    BINDINGS = [
        ("y", "approve", "Yes"),
        ("n", "deny", "No"),
        ("escape", "deny", "No"),
    ]

    def __init__(self, request: ConfirmationRequest) -> None:
        """Initialize.

        Args:
            request: The tool confirmation request.
        """
        super().__init__()
        self._request = request

    def compose(self) -> ComposeResult:
        """Build the confirmation dialog.

        Returns:
            ComposeResult with the dialog layout.
        """
        from rich.markup import escape

        colour = _RISK_COLOURS.get(self._request.risk_level, _DEFAULT_RISK_COLOUR)
        tool = escape(self._request.tool_name)
        desc = escape(self._request.description)
        params_label = self._build_params_label()

        yield Vertical(
            Label(
                f"[bold {colour}]⚠ Tool Approval Required[/]",
                id="confirm-title",
            ),
            Label(
                f"Tool [bold cyan]{tool}[/] wants to: {desc}",
                id="confirm-details",
            ),
            *params_label,
            Label(
                f"[dim]Risk level: [{colour}]" f"{self._request.risk_level}[/][/dim]"
            ),
            Vertical(
                Button(
                    "Yes  (y)",
                    variant="success",
                    id="btn-yes",
                ),
                Button(
                    "No   (n)",
                    variant="error",
                    id="btn-no",
                ),
                id="confirm-buttons",
            ),
            id="confirm-dialog",
        )

    def _build_params_label(self) -> list[Label]:
        """Build an optional parameters label.

        Returns:
            List containing zero or one ``Label`` widgets.
        """
        from rich.markup import escape

        if not self._request.params:
            return []
        try:
            text = json.dumps(self._request.params, indent=2)
        except (TypeError, ValueError):
            # Handle non-JSON-serializable parameters
            text = str(self._request.params)
        return [Label(f"[dim]Parameters:[/]\n" f"[yellow]{escape(text)}[/]")]

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Dismiss with the user's choice.

        Args:
            event: Button press event.
        """
        self.dismiss(event.button.id == "btn-yes")

    def action_approve(self) -> None:
        """Approve the tool call."""
        self.dismiss(True)

    def action_deny(self) -> None:
        """Deny the tool call."""
        self.dismiss(False)


# ------------------------------------------------------------------ #
# Help screen                                                          #
# ------------------------------------------------------------------ #


class HelpScreen(ModalScreen[None]):
    """Keybinding / help modal."""

    DEFAULT_CSS = """
    HelpScreen {
        align: center middle;
    }
    #help-dialog {
        padding: 2;
        border: solid $accent;
        background: $surface;
        width: 60;
        height: auto;
        align: center middle;
    }
    """
    BINDINGS = [("escape", "app.pop_screen", "Close")]

    def compose(self) -> ComposeResult:
        """Compose the help dialog.

        Returns:
            ComposeResult with help content.
        """
        yield Vertical(
            Label("[bold]Henchman-AI — Keybindings[/bold]"),
            Label(""),
            Label("[bold]Input[/bold]"),
            Label("  Enter          Submit message"),
            Label("  Shift+Enter    New line"),
            Label("  ↑ / ↓         Navigate history"),
            Label(""),
            Label("[bold]Search[/bold]"),
            Label("  Ctrl+F         Enter search mode"),
            Label("  F3             Next match"),
            Label("  Shift+F3       Previous match"),
            Label("  Escape         " "Exit search / close modal"),
            Label(""),
            Label("[bold]App[/bold]"),
            Label("  Ctrl+Q / Ctrl+C    Quit"),
            Label("  Ctrl+Shift+T       " "Clear thinking messages in chat"),
            Label("  Ctrl+Shift+Y       " "Clear tool messages in chat"),
            Label("  /               Slash command palette"),
            Label(""),
            Button(
                "Close",
                variant="primary",
                id="close-help",
            ),
            id="help-dialog",
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Close the help screen.

        Args:
            event: Button press event.
        """
        if event.button.id == "close-help":
            self.app.pop_screen()


# ------------------------------------------------------------------ #
# Provider selection screen                                            #
# ------------------------------------------------------------------ #


class ProviderScreen(ModalScreen[None]):
    """Provider selection modal."""

    DEFAULT_CSS = """
    ProviderScreen {
        align: center middle;
    }
    #provider-dialog {
        padding: 2;
        border: solid $accent;
        background: $surface;
        width: 60;
        height: auto;
    }
    #provider-select {
        margin: 1 0;
    }
    """
    BINDINGS = [("escape", "app.pop_screen", "Close")]

    def compose(self) -> ComposeResult:
        """Compose the provider dialog.

        Returns:
            ComposeResult with provider selection.
        """
        app: HenchmanTextualApp = self.app  # type: ignore[assignment]
        options = self._build_options(app.settings)
        current = self._current_provider_name(app.settings)
        current_in_options = any(v == current for _, v in options)
        select_value = current if current_in_options else Select.NULL

        yield Vertical(
            Label("[bold]Switch Provider[/bold]"),
            Label(f"Current: [cyan]{current}[/cyan]"),
            Select(
                options,
                id="provider-select",
                allow_blank=True,
                value=select_value,
            ),
            Vertical(
                Button(
                    "Switch",
                    variant="success",
                    id="btn-switch",
                ),
                Button(
                    "Cancel",
                    variant="default",
                    id="btn-cancel",
                ),
            ),
            id="provider-dialog",
        )

    @staticmethod
    def _build_options(
        settings: Any,
    ) -> list[tuple[str, str]]:
        """Build the provider option list from settings.

        Args:
            settings: Application settings object.

        Returns:
            List of (display_label, value) tuples.
        """
        options: list[tuple[str, str]] = []
        if not (settings and settings.providers):
            return [("No providers configured", "none")]
        ps = settings.providers
        for name in _KNOWN_PROVIDERS:
            cfg = getattr(ps, name, None)
            # Check if cfg is a non-empty dictionary
            if not isinstance(cfg, dict) or not cfg:
                continue
            # Safely get model name, default to provider name
            model = cfg.get("model") if isinstance(cfg, dict) else name
            if not isinstance(model, str):
                model = name
            options.append((f"{name} ({model})", name))
        if not options:
            return [("No providers configured", "none")]
        return options

    @staticmethod
    def _current_provider_name(settings: Any) -> str:
        """Get the current provider name from settings.

        Args:
            settings: Application settings object.

        Returns:
            Provider name string.
        """
        if settings and settings.providers:
            return settings.providers.default
        return "unknown"

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press.

        Args:
            event: Button press event.
        """
        if event.button.id == "btn-cancel":
            self.app.pop_screen()
            return
        if event.button.id != "btn-switch":
            return
        sel = self.query_one("#provider-select", Select)
        if sel.value and sel.value != Select.BLANK:
            self.app.post_message(SwitchProviderMessage(str(sel.value)))
        self.app.pop_screen()


# ------------------------------------------------------------------ #
# Session management screen                                            #
# ------------------------------------------------------------------ #


class SessionScreen(ModalScreen[str | None]):
    """Session management modal.

    Lists saved sessions and lets the user resume or delete them.
    Dismisses with the session tag/id to resume, or ``None`` if cancelled.
    """

    DEFAULT_CSS = """
    SessionScreen {
        align: center middle;
    }
    #session-dialog {
        padding: 2;
        border: solid $accent;
        background: $surface;
        width: 75;
        height: auto;
        max-height: 30;
    }
    #session-list {
        height: auto;
        max-height: 18;
        overflow-y: auto;
        margin: 1 0;
    }
    .session-entry {
        margin-bottom: 1;
    }
    """

    BINDINGS = [("escape", "cancel", "Close")]

    def __init__(self, sessions: list[Any] | None = None) -> None:
        """Initialize with an optional pre-loaded session list.

        Args:
            sessions: List of ``SessionMetadata`` (or dicts) to display.
                      Pass ``None`` to show an empty state.
        """
        super().__init__()
        self._sessions: list[Any] = sessions or []

    def compose(self) -> ComposeResult:
        """Build the session management dialog.

        Returns:
            ComposeResult with session list and action buttons.
        """
        entries = self._build_entries()
        options = [(label, sid) for label, sid in entries] if entries else []
        select_value = Select.NULL

        yield Vertical(
            Label("[bold]Session Management[/bold]"),
            Label(f"[dim]{len(self._sessions)} saved session(s)[/dim]"),
            Select(
                options if options else [("No sessions", "none")],
                id="session-select",
                allow_blank=True,
                value=select_value,
            ),
            Vertical(
                Button("Resume", variant="success", id="btn-resume"),
                Button("Delete", variant="error", id="btn-delete"),
                Button("Cancel", variant="default", id="btn-cancel"),
            ),
            id="session-dialog",
        )

    def _build_entries(self) -> list[tuple[str, str]]:
        """Build display entries from session list.

        Returns:
            List of (display_label, session_id) tuples.
        """
        entries: list[tuple[str, str]] = []
        for sess in self._sessions:
            tag = getattr(sess, "tag", None) or getattr(sess, "id", "unknown")
            ts = getattr(sess, "updated_at", None) or getattr(sess, "created_at", "")
            count = getattr(sess, "message_count", 0)
            label = f"{tag}  [{ts}]  ({count} messages)"
            sid = str(getattr(sess, "id", tag))
            entries.append((label, sid))
        return entries

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses.

        Args:
            event: Button press event.
        """
        if event.button.id == "btn-cancel":
            self.dismiss(None)
            return
        sel = self.query_one("#session-select", Select)
        value = str(sel.value) if sel.value and sel.value != Select.BLANK else None
        if event.button.id == "btn-resume" and value and value != "none":
            self.dismiss(f"resume:{value}")
        elif event.button.id == "btn-delete" and value and value != "none":
            self.dismiss(f"delete:{value}")
        else:
            self.dismiss(None)

    def action_cancel(self) -> None:
        """Cancel and close."""
        self.dismiss(None)
