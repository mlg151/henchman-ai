"""Serialized Textual question and approval dialogs with cancellable lifetimes."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any, ClassVar, cast

from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label

from henchman.cli.textual_screens import ConfirmToolScreen

if TYPE_CHECKING:
    from textual.app import App, ComposeResult
    from textual.binding import Binding

    from henchman.tools.base import ConfirmationRequest


class _PromptLifetime:
    """Retire an obscured prompt when it resumes, preserving unrelated overlays."""

    expired: bool = False

    def _init_lifetime(self) -> None:
        self.removed = asyncio.Event()

    def expire(self) -> None:
        """Disable further answers and dismiss only when this prompt is current."""
        self.expired = True
        self._dismiss_if_expired()

    def _dismiss_if_expired(self) -> None:
        screen = cast("ModalScreen[object]", self)
        if self.expired and screen.app.screen is screen:
            screen.dismiss(None)

    def on_screen_resume(self) -> None:
        """Remove a timed-out prompt once any unrelated overlay closes."""
        self._dismiss_if_expired()

    def on_unmount(self) -> None:
        """Release a queued prompt after removal from the screen stack."""
        self.removed.set()


class QuestionScreen(_PromptLifetime, ModalScreen[str | None]):
    """Collect one actual answer, with Escape representing no answer."""

    DEFAULT_CSS = """
    QuestionScreen { align: center middle; }
    #question-dialog {
        width: 70; max-width: 95%; height: auto;
        padding: 1 2; border: solid $accent; background: $surface;
    }
    #tool-question { width: 100%; height: auto; margin-bottom: 1; }
    #question-actions { height: auto; align-horizontal: right; margin-top: 1; }
    """
    BINDINGS: ClassVar[list[Binding | tuple[str, str] | tuple[str, str, str]]] = [
        ("escape", "cancel", "Cancel"),
    ]

    def __init__(self, question: str) -> None:
        super().__init__()
        self._init_lifetime()
        self.question = question

    def compose(self) -> ComposeResult:
        """Render literal question text and a focused answer field."""
        yield Vertical(
            Label(self.question, markup=False, id="tool-question"),
            Input(placeholder="Your answer", id="question-answer"),
            Horizontal(
                Button("Answer", variant="primary", id="question-submit"),
                Button("Cancel", id="question-cancel"),
                id="question-actions",
            ),
            id="question-dialog",
        )

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Submit nonblank input without changing the user's text."""
        event.stop()
        self._submit()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Route answer and cancel buttons."""
        event.stop()
        if event.button.id == "question-submit":
            self._submit()
        else:
            self.action_cancel()

    def _submit(self) -> None:
        answer = self.query_one(Input).value
        if not self.expired and answer.strip():
            self.dismiss(answer)

    def action_cancel(self) -> None:
        """Close without supplying an answer."""
        self.dismiss(None)


class _ApprovalScreen(_PromptLifetime, ConfirmToolScreen):
    """Reuse the existing approval UI with prompt cancellation cleanup."""

    def __init__(self, request: ConfirmationRequest) -> None:
        super().__init__(request)
        self._init_lifetime()


class ToolPromptChannel:
    """Keep one tool dialog active and cancel pending input during shutdown."""

    def __init__(self, app: App[Any]) -> None:
        self.app = app
        self._lock = asyncio.Lock()
        self._screen: QuestionScreen | _ApprovalScreen | None = None
        self._answer: asyncio.Future[object] | None = None
        self._closed = False

    async def ask(self, question: str) -> str | None:
        """Wait for an answer through the Textual input widget."""
        result = await self._show(QuestionScreen(question))
        return result if isinstance(result, str) else None

    async def confirm(self, request: ConfirmationRequest) -> bool:
        """Serialize approvals with questions and require explicit approval."""
        return await self._show(_ApprovalScreen(request)) is True

    async def _show(self, screen: QuestionScreen | _ApprovalScreen) -> object:
        async with self._lock:
            if self._closed:
                raise asyncio.CancelledError
            # A cancelled prompt beneath an unrelated overlay retires on resume.
            # Do not stack a new tool prompt above that overlay in the meantime.
            if self._screen is not None:
                await self._screen.removed.wait()
            if self._closed:
                raise asyncio.CancelledError
            future: asyncio.Future[object] = asyncio.get_running_loop().create_future()
            self._screen = screen
            self._answer = future

            def answered(result: object) -> None:
                if not future.done():
                    future.set_result(result)

            try:
                await self.app.push_screen(screen, answered)
                return await future
            finally:
                self._answer = None
                future.cancel()
                if screen in self.app.screen_stack:
                    screen.expire()
                elif not screen.is_mounted:
                    screen.removed.set()

    def close(self) -> None:
        """Cancel input and unblock queued tasks when the app shuts down."""
        self._closed = True
        if self._answer is not None:
            self._answer.cancel()
        if self._screen is not None:
            self._screen.removed.set()
