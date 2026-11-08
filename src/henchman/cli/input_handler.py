"""Input handler for REPL.

This module handles user input processing including prompt sessions,
@file expansion, and shell command detection.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Any

try:
    from typing import Self
except ImportError:
    from typing import Self

from prompt_toolkit.application import get_app_or_none
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.document import Document

from henchman.cli.commands.builtins import get_builtin_commands
from henchman.cli.draft_editor import (
    DraftBinding,
    DraftEditorError,
    check_editor_control,
    edit_draft,
    join_owned,
)
from henchman.cli.input import create_session, expand_at_references, is_slash_command
from henchman.cli.workflow import idle_command
from henchman.utils.evidence_redaction import EvidenceRedactor

if TYPE_CHECKING:
    from collections.abc import Callable

    from prompt_toolkit import Application, PromptSession

    from henchman.cli.repl import ReplConfig
    from henchman.tools.registry import ToolRegistry


@asynccontextmanager
async def _editor_terminal(app: Application[Any]) -> AsyncIterator[None]:
    """Suspend the composer, including safe cancellation *before* tty entry.

    prompt-toolkit's in_terminal publishes a serialization future before its
    early awaits, outside its cleanup block. Own that interval here so a stop
    during prior output/CPR waits cannot cancel prior work or strand the chain.
    """
    if not app.is_running:
        yield
        return
    previous = app._running_in_terminal_f
    owned: asyncio.Future[None] = asyncio.get_running_loop().create_future()
    app._running_in_terminal_f = owned
    entered = False
    primary: BaseException | None = None

    def release(_previous: asyncio.Future[None] | None = None) -> None:
        if not owned.done():
            owned.set_result(None)

    try:
        if previous is not None:
            await asyncio.shield(previous)
        if app.output.responds_to_cpr:
            await app.renderer.wait_for_cpr_responses()
        app.renderer.erase()
        app._running_in_terminal = True
        entered = True
        with app.input.detach(), app.input.cooked_mode():
            yield
    except BaseException as error:
        primary = error
        raise
    finally:
        try:
            if entered:
                app._running_in_terminal = False
                app.renderer.reset()
                app._request_absolute_cursor_position()
                app._redraw()
        except BaseException:
            if primary is None:
                raise
            primary.add_note("Composer terminal restoration also failed.")
        finally:
            # Preserve the existing owner's serialization even when this edit
            # is cancelled before entering it. This callback owns no task.
            if previous is not None and not previous.done():
                previous.add_done_callback(release)
            else:
                release()


class InputHandler:
    """Handles user input processing for the REPL.

    Responsibilities:
    - Manage prompt sessions
    - Handle @file expansion
    - Detect shell commands
    - Get user input with proper error handling
    """

    def __init__(
        self: Self,
        config: ReplConfig,
        renderer: object,
        history_file: Path | None = None,
        keybindings: dict[str, str] | None = None,
        tool_registry: ToolRegistry | None = None,
        evidence_redactor: EvidenceRedactor | None = None,
        keyboard_mode: str = "standard",
        editor_frontend: Any = None,
    ) -> None:
        """Initialize the input handler.

        Args:
            config: REPL configuration.
            renderer: UI renderer for output.
            history_file: Path to history file.
            keybindings: Custom keybindings configuration.
            tool_registry: Optional tool registry for tool name completions.
            evidence_redactor: Shared policy for persisted prompt history.
            keyboard_mode: Startup editing profile for the main composer.
        """
        self.config = config
        self.renderer = renderer
        self.history_file = history_file or Path.home() / ".henchman_history"
        self.keybindings = keybindings
        self.tool_registry = tool_registry
        self.evidence_redactor = evidence_redactor
        self.keyboard_mode = keyboard_mode
        self.prompt_session: PromptSession[str] | None = None
        self.editor_frontend = editor_frontend
        self._editor_task: asyncio.Task[None] | None = None
        self._editor_close_task: asyncio.Task[None] | None = None
        self._editor_closed = False
        self._editor_previous_idle: object = None
        self._editor_recovery: tuple[str, DraftBinding] | None = None

    def initialize_prompt_session(
        self,
        bottom_toolbar: Callable[[], list[tuple[str, str]]] | None = None,
    ) -> None:
        """Initialize the prompt session.

        Args:
            bottom_toolbar: Function to generate bottom toolbar content.

        Returns:
            None
        """
        # Create completer for commands and tools
        commands = [f"/{cmd.name}" for cmd in get_builtin_commands()]

        # Add tools to completion list when available
        tools = []
        if self.tool_registry and hasattr(self.tool_registry, "list_tools"):
            tools = [f"!{tool}" for tool in self.tool_registry.list_tools()]

        completer = WordCompleter(commands + tools, ignore_case=True)

        self.prompt_session = create_session(
            self.history_file,
            bottom_toolbar=bottom_toolbar,
            keybindings=self.keybindings,
            completer=completer,
            evidence_redactor=self.evidence_redactor,
            keyboard_mode=self.keyboard_mode,
            editor_action=self.start_external_editor if self.editor_frontend is not None else None,
        )

    @property
    def editor_active(self) -> bool:
        return self._editor_task is not None and not self._editor_task.done()

    def start_external_editor(self) -> None:
        """F11 reserves one explicit composer edit, never an execution input."""
        if self._editor_closed or self.editor_active or self.prompt_session is None:
            return
        application = get_app_or_none()
        if application is None or not application.is_running or application.current_buffer is not self.prompt_session.default_buffer:
            self._editor_notice("External editor requires the active composer.")
            return
        try:
            binding = DraftBinding.capture(self.editor_frontend)
        except DraftEditorError as error:
            self._editor_notice(str(error))
            return
        self._editor_previous_idle = getattr(self.editor_frontend, "_idle_control_task", None)
        self._editor_task = application.create_background_task(self._edit(binding, application))
        self.editor_frontend._idle_control_task = self._editor_task

    def _editor_notice(self, message: str) -> None:
        warning = getattr(self.renderer, "warning", None)
        if callable(warning):
            warning(message)

    async def _edit(self, binding: DraftBinding, application: Application[Any]) -> None:
        assert self.prompt_session is not None
        frontend = self.editor_frontend
        prompt = self.prompt_session
        buffer = prompt.default_buffer
        original, selection = buffer.document, buffer.selection_state

        def authorize() -> None:
            binding.check(frontend)
            if self._editor_closed:
                raise DraftEditorError("External editor session changed or is closing.")

        try:
            authorize()
            with idle_command(frontend):
                async with _editor_terminal(application):
                    authorize()
                    if self._editor_recovery is not None:
                        from prompt_toolkit import PromptSession

                        held, held_binding = self._editor_recovery
                        recovery: PromptSession[str] = PromptSession(input=prompt.input, output=prompt.output)
                        answer = await recovery.prompt_async(
                            "Edited text is held in memory. Replace current draft [use], discard [discard], or return [Enter]: ",
                        )
                        authorize()
                        if answer.strip().lower() == "discard":
                            self._editor_recovery = None
                            return
                        if answer.strip().lower() != "use":
                            return
                        held_binding.check(frontend)
                        if buffer.text != original.text:
                            raise DraftEditorError("Return to the original session and review the current draft first.")
                        result = held
                        self._editor_recovery = None
                    else:
                        result = await edit_draft(original.text, cwd=binding.root, authorize=authorize)
                try:
                    authorize()
                    if buffer.text != original.text:
                        raise DraftEditorError("Draft changed.")
                except DraftEditorError:
                    self._editor_recovery = (result, binding)
                    self._editor_notice("Edited text is held in memory. Press F11 to review or discard it.")
                else:
                    await check_editor_control()
                    buffer.document = Document(result, cursor_position=len(result))
                    self._editor_notice("Draft updated; review it before sending.")
        except (asyncio.CancelledError, KeyboardInterrupt, EOFError):
            if not self._editor_closed:
                self._editor_notice("External editor cancelled; original draft preserved.")
        except DraftEditorError as error:
            self._editor_notice(str(error))
        except Exception:
            self._editor_notice("External editor unavailable or failed; original draft preserved. Check VISUAL/EDITOR, terminal and idle policy.")
        finally:
            if getattr(frontend, "_idle_control_task", None) is asyncio.current_task():
                frontend._idle_control_task = self._editor_previous_idle
            if buffer.text == original.text:
                buffer.document = original
                buffer.selection_state = selection

    def cancel_editor(self) -> bool:
        if self.editor_active and self._editor_task is not None:
            if not self._editor_task.cancelling():
                self._editor_task.cancel()
            return True
        return False

    async def close_editor(self) -> None:
        """Join editor cleanup independently from cancellation of the REPL caller."""
        if self._editor_close_task is None:
            self._editor_closed = True
            async def finish() -> None:
                self.cancel_editor()
                if self._editor_task is not None:
                    await asyncio.gather(self._editor_task, return_exceptions=True)
                self._editor_recovery = None
            self._editor_close_task = asyncio.create_task(finish())
        failure = await join_owned(self._editor_close_task)
        if failure is not None:
            raise failure

    async def get_input(self: Self) -> str:
        """Get input from the user.

        Returns:
            User input string.

        Raises:
            RuntimeError: If prompt session is not initialized.
            KeyboardInterrupt: If user presses Ctrl+C.
            EOFError: If user presses Ctrl+D.
        """
        if not self.prompt_session:
            msg = (
                "Prompt session not initialized. "
                "Call initialize_prompt_session() before get_input()."
            )
            raise RuntimeError(
                msg,
            )

        # Ensure a fresh line for the prompt
        if hasattr(self.renderer, "print_newline"):
            self.renderer.print_newline()
        return await self.prompt_session.prompt_async(self.config.prompt)

    async def ask_question(self, question: str) -> str | None:
        """Read a literal answer without command expansion or command history."""
        from prompt_toolkit import PromptSession

        if self.prompt_session is None:
            raise RuntimeError("Prompt session not initialized")
        session: PromptSession[str] = PromptSession(
            input=self.prompt_session.input,
            output=self.prompt_session.output,
        )
        try:
            return await session.prompt_async(f"{question}\nAnswer: ")
        except EOFError:
            return None
        except KeyboardInterrupt as exc:
            raise asyncio.CancelledError from exc

    def is_slash_command(self: Self, input_text: str) -> bool:
        """Check if input is a slash command.

        Args:
            input_text: The input text to check.

        Returns:
            True if input is a slash command.
        """
        return is_slash_command(input_text)

    async def expand_at_references(self: Self, input_text: str) -> str:
        """Expand @file references in input.

        Args:
            input_text: The input text to expand.

        Returns:
            Expanded input text.
        """
        return await expand_at_references(input_text)

    async def process_input(self: Self, user_input: str) -> tuple[str, bool, bool]:
        """Process user input to determine if it's a command or regular input.

        Args:
            user_input: The raw user input.

        Returns:
            Tuple of (processed_input, is_command, should_continue)
            - processed_input: Expanded input text (if not a command)
            - is_command: True if input is a slash command
            - should_continue: True if REPL should continue running (False to exit)
        """
        stripped = user_input.strip()
        if not stripped:
            return "", False, True

        if self.is_slash_command(stripped):
            # For slash commands, return the command text
            # REPL will handle actual command execution
            return stripped, True, True

        # Expand @file references for regular input
        expanded = await self.expand_at_references(stripped)
        return expanded, False, True
