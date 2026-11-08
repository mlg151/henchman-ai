"""Modal screens for the Henchman-AI Textual TUI.

Includes tool-confirmation, help/keybinding, and provider-selection
modals.

Note: Extracted from ``textual_app.py`` to keep modules under 500 lines.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, ClassVar

from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Select

from henchman.cli.textual_messages import SwitchProviderMessage
from henchman.cli.textual_sessions import SessionScreen as SessionScreen

if TYPE_CHECKING:
    from textual.app import ComposeResult
    from textual.binding import Binding

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
        max-width: 95%;
        height: auto;
        max-height: 95%;
    }
    #confirm-title {
        text-style: bold;
        margin-bottom: 1;
    }
    #confirm-details {
        margin-bottom: 1;
        color: $text-muted;
        max-height: 3;
        overflow: hidden;
    }
    #confirm-params {
        max-height: 5;
        overflow: hidden;
    }
    #confirm-buttons {
        align: right middle;
        height: auto;
        margin-top: 1;
    }
    """

    BINDINGS: ClassVar[list[Binding | tuple[str, str] | tuple[str, str, str]]] = [
        ("y", "approve", "Yes"),
        ("n", "deny", "No"),
        ("escape", "deny", "No"),
        ("f10", "review", "Inspect / Export"),
    ]

    def __init__(self: ConfirmToolScreen, request: ConfirmationRequest) -> None:
        """Initialize.

        Args:
            request: The tool confirmation request.
        """
        super().__init__()
        self._request: ConfirmationRequest = request

    def compose(self: ConfirmToolScreen) -> ComposeResult:
        """Build the confirmation dialog.

        Returns:
            ComposeResult with the dialog layout.
        """
        yield self._build_confirmation_dialog()

    def _build_confirmation_dialog(self: ConfirmToolScreen) -> Vertical:
        """Build the confirmation dialog widget.

        Returns:
            Vertical container with the dialog layout.
        """
        from rich.markup import escape
        from textual._context import NoActiveAppError

        from henchman.cli.textual_context import _current_policy
        from henchman.cli.textual_questions import _approval_evidence
        from henchman.utils.evidence_redaction import EvidenceRedactor

        try:
            policy = _current_policy(self.app)
        except NoActiveAppError:
            policy = EvidenceRedactor()
        self._request = _approval_evidence(self._request, policy)

        colour = _RISK_COLOURS.get(self._request.risk_level, _DEFAULT_RISK_COLOUR)
        tool = escape(self._request.tool_name)
        desc = escape(self._request.description)
        params_label = self._build_params_label()

        return Vertical(
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
                f"[dim]Risk level: [{colour}]{self._request.risk_level}[/][/dim]",
            ),
            self._build_action_buttons(),
            id="confirm-dialog",
        )

    def _build_action_buttons(self: ConfirmToolScreen) -> Horizontal:
        """Build the approve/deny button group.

        Returns:
            Horizontal container with review, Yes and No buttons.
        """
        return Horizontal(
            Button("Review (F10)", id="decision-review"),
            Button("Yes  (y)", variant="success", id="btn-yes"),
            Button("No   (n)", variant="error", id="btn-no"),
            id="confirm-buttons",
        )

    def _build_params_label(self: ConfirmToolScreen) -> list[Label]:
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
        return [
            Label(
                f"[dim]Parameter preview; Review (F10) shows retained details:[/]\n[yellow]{escape(text)}[/]",
                id="confirm-params",
            )
        ]

    def on_button_pressed(self: ConfirmToolScreen, event: Button.Pressed) -> None:
        """Dismiss with the user's choice.

        Args:
            event: Button press event.

        Returns:
            None
        """
        if event.button.id == "decision-review":
            event.stop()
            self.action_review()
        else:
            self.dismiss(event.button.id == "btn-yes")

    def action_review(self) -> None:
        from henchman.cli.textual_review import open_decision_review

        open_decision_review(self)

    def action_approve(self: ConfirmToolScreen) -> None:
        """Approve the tool call.

        Returns:
            None
        """
        self.dismiss(result=True)

    def action_deny(self: ConfirmToolScreen) -> None:
        """Deny the tool call.

        Returns:
            None
        """
        self.dismiss(result=False)


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
    BINDINGS: ClassVar[list[Binding | tuple[str, str] | tuple[str, str, str]]] = [
        ("escape", "app.pop_screen", "Close"),
    ]

    def compose(self: HelpScreen) -> ComposeResult:
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
            Label("[bold]Search / transcript[/bold]"),
            Label("  Ctrl+F Search; F3 / Shift+F3 Next / previous"),
            Label("  Alt+PageUp / Alt+PageDown  Read transcript"),
            Label("  Alt+End        Return to live"),
            Label("  Escape         Exit search / close modal"),
            Label(""),
            Label("[bold]App[/bold]"),
            Label("  Ctrl+Q / Ctrl+C    Quit"),
            Label("  F4                Return to pending question or approval"),
            Label("  F9                Inspect and control saved input queue"),
            Label("  F8                Review captured file changes"),
            Label("  F10              Inspect/export a pending decision"),
            Label("  F11              Edit unsent draft in VISUAL/EDITOR"),
            Label("  Context → Sessions    Search, inspect and explicitly resume"),
            Label("  Ctrl+Shift+T       Clear thinking messages in chat"),
            Label("  Ctrl+Shift+Y       Clear tool messages in chat"),
            Label("  /               Slash command palette"),
            Label(""),
            Button(
                "Close",
                variant="primary",
                id="close-help",
            ),
            id="help-dialog",
        )

    def on_button_pressed(self: HelpScreen, event: Button.Pressed) -> None:
        """Close the help screen.

        Args:
            event: Button press event.

        Returns:
            None
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
    BINDINGS: ClassVar[list[Binding | tuple[str, str] | tuple[str, str, str]]] = [
        ("escape", "app.pop_screen", "Close"),
    ]

    def compose(self: ProviderScreen) -> ComposeResult:
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
        if settings and hasattr(settings, "providers") and settings.providers:
            return str(settings.providers.default)
        return "unknown"

    def on_button_pressed(self: ProviderScreen, event: Button.Pressed) -> None:
        """Handle button press.

        Args:
            event: Button press event.

        Returns:
            None
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


# ------------------------------------------------------------------ #
# Auto mode screen                                                     #
# ------------------------------------------------------------------ #


class AutoModeScreen(ModalScreen[bool]):
    """Modal dialog for enabling/disabling auto mode."""

    DEFAULT_CSS = """
    AutoModeScreen {
        align: center middle;
    }
    #auto-mode-dialog {
        padding: 2;
        border: solid $accent;
        background: $surface;
        width: 60;
        height: auto;
    }
    #auto-mode-buttons {
        align: center middle;
        padding-top: 1;
    }
    """

    def on_button_pressed(self: AutoModeScreen, event: Button.Pressed) -> None:
        """Dismiss with the user's choice.

        Args:
            event: Button press event.

        Returns:
            None
        """
        self.dismiss(event.button.id == "btn-enable")

    def compose(self: AutoModeScreen) -> ComposeResult:
        """Create child widgets for the auto mode screen.

        Yields:
            Widget instances for the auto-mode dialog.
        """
        from textual.containers import Horizontal
        from textual.widgets import Button, Label

        yield Vertical(
            Label("Auto Mode", id="auto-mode-title"),
            Label(
                "Enable auto mode? The agent will automatically execute "
                "approved tools without confirmation.",
            ),
            Horizontal(
                Button("Enable", id="btn-enable", variant="primary"),
                Button("Cancel", id="btn-cancel", variant="default"),
                id="auto-mode-buttons",
            ),
            id="auto-mode-dialog",
        )


# ------------------------------------------------------------------ #
# Bridge screen                                                        #
# ------------------------------------------------------------------ #


class BridgeScreen(ModalScreen[str | None]):
    """Modal screen for bridge configuration."""

    DEFAULT_CSS = """
    BridgeScreen {
        align: center middle;
    }
    #bridge-dialog {
        padding: 2;
        border: solid $accent;
        background: $surface;
        width: 80;
        height: auto;
        max-height: 30;
    }
    """

    BINDINGS: ClassVar[list[Binding | tuple[str, str] | tuple[str, str, str]]] = [
        ("escape", "cancel", "Close"),
    ]

    def __init__(self: BridgeScreen, bridge_entries: list[str] | None = None) -> None:
        """Initialize with persisted bridge descriptions."""

        super().__init__()
        self._bridge_entries = self._build_entries(bridge_entries or [])

    def compose(self: BridgeScreen) -> ComposeResult:
        """Build the bridge listing dialog."""

        from rich.markup import escape

        entries = "\n".join(escape(entry) for entry in self._bridge_entries)
        if not entries:
            entries = "[dim]No persisted bridges.[/]"
        yield Vertical(
            Label("[bold]Team Bridges[/bold]"),
            Label(entries, id="bridge-entries"),
            Button("Close", id="btn-close", variant="primary"),
            id="bridge-dialog",
        )

    def on_button_pressed(self: BridgeScreen, _event: Button.Pressed) -> None:
        """Close the bridge listing."""

        self.dismiss(None)

    def action_cancel(self: BridgeScreen) -> None:
        """Close the bridge listing."""

        self.dismiss(None)

    @staticmethod
    def _build_entries(
        bridge_entries: list[str],
    ) -> list[str]:
        """Build bridge entry options from metadata.

        Args:
            bridge_entries: Bridge connection description strings.

        Returns:
            List of bridge entry description strings.
        """
        return list(bridge_entries)


# ------------------------------------------------------------------ #
# Export screen                                                        #
# ------------------------------------------------------------------ #


class ExportScreen(ModalScreen[str | None]):
    """Modal screen for export options."""

    DEFAULT_CSS = """
    ExportScreen {
        align: center middle;
    }
    #export-dialog {
        padding: 2;
        border: solid $accent;
        background: $surface;
        width: 60;
        height: auto;
    }
    """

    BINDINGS: ClassVar[list[Binding | tuple[str, str] | tuple[str, str, str]]] = [
        ("escape", "cancel", "Close"),
    ]

    def compose(self: ExportScreen) -> ComposeResult:
        """Build the session export dialog."""

        yield Vertical(
            Label("[bold]Export Active Session[/bold]"),
            Label("Write the active session to Markdown in the current project."),
            Horizontal(
                Button("Export Markdown", id="btn-markdown", variant="primary"),
                Button("Cancel", id="btn-cancel"),
            ),
            id="export-dialog",
        )

    def on_button_pressed(self: ExportScreen, event: Button.Pressed) -> None:
        """Handle button press events.

        Strips the ``btn-`` prefix for cleaner dismiss values.

        Args:
            event: Button press event.

        Returns:
            None
        """
        btn_id = event.button.id or ""
        self.dismiss("markdown" if btn_id == "btn-markdown" else None)

    def action_cancel(self: ExportScreen) -> None:
        """Cancel the export."""

        self.dismiss(None)


# ------------------------------------------------------------------ #
# Feedback screen                                                      #
# ------------------------------------------------------------------ #


class FeedbackScreen(ModalScreen[str | None]):
    """Modal screen for collecting user feedback."""

    DEFAULT_CSS = """
    FeedbackScreen {
        align: center middle;
    }
    #feedback-dialog {
        padding: 2;
        border: solid $accent;
        background: $surface;
        width: 60;
        height: auto;
    }
    """

    def on_button_pressed(self: FeedbackScreen, event: Button.Pressed) -> None:
        """Handle button press events.

        Dismisses with the current ``Select`` value when submitting.

        Args:
            event: Button press event.

        Returns:
            None
        """
        if event.button.id == "btn-submit":
            select = self.query_one(Select)
            self.dismiss(str(select.value) if select.value is not None else None)
        else:
            self.dismiss(None)


# ------------------------------------------------------------------ #
# History search screen                                                #
# ------------------------------------------------------------------ #


class HistorySearchScreen(ModalScreen[str | None]):
    """Modal screen for searching conversation history."""

    DEFAULT_CSS = """
    HistorySearchScreen {
        align: center middle;
    }
    """

    @staticmethod
    def _build_options(
        prompts: list[str] | None = None,
    ) -> list[tuple[str, str]]:
        """Build history search options from recent prompts.

        Args:
            prompts: Recent conversation prompts (most recent last).

        Returns:
            List of (label, value) tuples, most recent first.
        """
        if prompts:
            return [(p, p) for p in reversed(prompts)]
        return [
            ("Last 10 messages", "last_10"),
            ("Last 50 messages", "last_50"),
            ("Last 100 messages", "last_100"),
            ("All messages", "all"),
        ]


# ------------------------------------------------------------------ #
# MCP servers screen                                                   #
# ------------------------------------------------------------------ #


class McpServersScreen(ModalScreen[str | None]):
    """Modal screen for viewing and managing MCP server connections."""

    DEFAULT_CSS = """
    McpServersScreen {
        align: center middle;
    }
    """

    @staticmethod
    def _build_entries(
        configured: list[str] | None = None,
        connected: list[str] | None = None,
    ) -> list[tuple[str, str]]:
        """Build MCP server entry options from configs.

        Args:
            configured: List of configured server names.
            connected: List of connected server names.

        Returns:
            List of (label, value) tuples for selection.
        """
        configured = configured or []
        connected = connected or []
        entries: list[tuple[str, str]] = []
        for name in configured:
            status = "connected" if name in connected else "disconnected"
            entries.append((f"{name} ({status})", name))
        return entries


# ------------------------------------------------------------------ #
# Model picker screen                                                  #
# ------------------------------------------------------------------ #


class ModelPickerScreen(ModalScreen[str | None]):
    """Modal screen for selecting a model provider."""

    DEFAULT_CSS = """
    ModelPickerScreen {
        align: center middle;
    }
    """

    @staticmethod
    def _build_options(settings: object) -> list[tuple[str, str]]:
        """Build model picker options from settings.

        Args:
            settings: Application settings object.

        Returns:
            List of (label, value) tuples.
        """
        options: list[tuple[str, str]] = []
        if not settings:
            return options
        providers = getattr(settings, "providers", None)
        if not providers:
            return options
        for provider_name in ("deepseek", "anthropic", "ollama", "openai"):
            cfg = getattr(providers, provider_name, None)
            if not isinstance(cfg, dict) or not cfg:
                continue
            model = cfg.get("model") if isinstance(cfg, dict) else None
            if model:
                options.append((f"{provider_name} ({model})", provider_name))
        return options


# ------------------------------------------------------------------ #
# Onboarding screen                                                    #
# ------------------------------------------------------------------ #


class OnboardingScreen(ModalScreen[str | None]):
    """Modal screen for first-time setup wizard."""

    DEFAULT_CSS = """
    OnboardingScreen {
        align: center middle;
    }
    #onboarding-dialog {
        padding: 2;
        border: solid $accent;
        background: $surface;
        width: 70;
        height: auto;
    }
    """

    BINDINGS: ClassVar[list[Binding | tuple[str, str] | tuple[str, str, str]]] = [
        ("escape", "cancel", "Close"),
    ]

    def compose(self: OnboardingScreen) -> ComposeResult:
        """Build the first-run navigation dialog."""

        yield Vertical(
            Label("[bold]Welcome to Henchman-AI[/bold]"),
            Label("Choose where to continue setup."),
            Horizontal(
                Button("Workspace", id="btn-settings", variant="primary"),
                Button("Theme", id="btn-theme"),
                Button("Close", id="btn-cancel"),
            ),
            id="onboarding-dialog",
        )

    def on_button_pressed(self: OnboardingScreen, event: Button.Pressed) -> None:
        """Handle button press events.

        Strips the ``btn-`` prefix for simpler dismiss values.

        Args:
            event: Button press event.

        Returns:
            None
        """
        btn_id = event.button.id or ""
        if btn_id == "btn-cancel":
            self.dismiss(None)
            return
        value = btn_id.removeprefix("btn-") if btn_id.startswith("btn-") else btn_id
        self.dismiss(value)

    def action_cancel(self: OnboardingScreen) -> None:
        """Close onboarding without changing views."""

        self.dismiss(None)


# ------------------------------------------------------------------ #
# Search screen                                                        #
# ------------------------------------------------------------------ #


class SearchScreen(ModalScreen[str | None]):
    """Modal screen for semantic code search."""

    DEFAULT_CSS = """
    SearchScreen {
        align: center middle;
    }
    #search-dialog {
        padding: 2;
        border: solid $accent;
        background: $surface;
        width: 60;
        height: auto;
    }
    #search-buttons {
        align: center middle;
        padding-top: 1;
    }
    """

    def on_button_pressed(self: SearchScreen, event: Button.Pressed) -> None:
        """Handle button press events.

        Args:
            event: Button press event.
        """
        btn_id = event.button.id
        if btn_id == "btn-search":
            inp = self.query_one(Input)
            self.dismiss(inp.value)
        elif btn_id == "btn-clear":
            self.dismiss("")
        else:
            self.dismiss(None)


# ------------------------------------------------------------------ #
# Theme picker screen                                                  #
# ------------------------------------------------------------------ #


class ThemePickerScreen(ModalScreen[str | None]):
    """Modal screen for selecting a UI theme."""

    DEFAULT_CSS = """
    ThemePickerScreen {
        align: center middle;
    }
    """

    @staticmethod
    def _build_options() -> list[tuple[str, str]]:
        """Build theme picker options.

        Returns:
            List of (label, value) tuples.
        """
        return [
            ("Dark", "dark"),
            ("Light", "light"),
            ("Monokai", "monokai"),
            ("Dracula", "dracula"),
        ]
