"""Transient OAuth actions owned by fresh interactive frontend submissions."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

if TYPE_CHECKING:
    from henchman.cli.oauth import OAuthAction, OAuthIntent, OAuthRuntimeView

OAUTH_COMMAND_GUIDANCE = (
    "Submit /mcp auth <status|login|refresh|logout> <server> or /mcp connect <server> "
    "directly in the interactive prompt. Saved or programmatic commands cannot authorize authentication."
)
OAUTH_ACCEPTED_LABEL = "/mcp auth [interactive request omitted]"


def is_oauth_command(text: str) -> bool:
    """Recognize even malformed candidates before history, echo or queue routing."""
    parts = text.strip().split(maxsplit=2)
    return len(parts) >= 2 and parts[0].lower() == "/mcp" and parts[1].lower() in {"auth", "connect"}


def oauth_command_evidence(text: str) -> str:
    """Hide arguments even when a saved/programmatic command is refused."""
    return OAUTH_ACCEPTED_LABEL if is_oauth_command(text) else text


def _parse(text: str) -> tuple[OAuthAction, str]:
    parts = text.strip().split()
    if len(text.encode("utf-8")) > 4096:
        raise ValueError
    if len(parts) == 3 and parts[0].lower() == "/mcp" and parts[1].lower() == "connect":
        return "connect", parts[2]
    if (len(parts) == 4 and parts[0].lower() == "/mcp" and parts[1].lower() == "auth"
        and parts[2].lower() in {"status", "login", "refresh", "logout"}):
        return cast("OAuthAction", parts[2].lower()), parts[3]
    raise ValueError


@dataclass(frozen=True, repr=False)
class _ActionRuntime:
    view: OAuthRuntimeView
    session_key: tuple[object, object]
    project_identity: tuple[int, int]


class FrontendOAuth:
    """Own action tasks without granting persisted commands a route to intent.

    Only the terminal-read and composer-submit handlers call ``submit``. The
    controller is retained for connection guards after an action finishes.
    """

    def __init__(self, frontend: Any, project_root: Path, *, emit: Callable[[str], None],
                 settled: Callable[[bool], None]) -> None:
        from henchman.cli.oauth import OAuthController

        self._frontend = frontend
        self._project_root = project_root.resolve()
        self._context = getattr(frontend, "core_context", None)
        self._emit = emit
        self._settled = settled
        self._closed = False
        self._tasks: dict[asyncio.Task[None], _ActionRuntime] = {}
        self._network_task: asyncio.Task[None] | None = None
        self.controller = OAuthController(self._view)

    def _view(self) -> OAuthRuntimeView:
        from henchman.cli.oauth import OAuthRuntimeView
        from henchman.cli.output_handler import resolve_active_agent
        from henchman.cli.workflow import frontend_has_active_work
        from henchman.mcp.oauth import OAuthError

        frontend = self._frontend
        context = getattr(frontend, "core_context", None)
        if context is not self._context:
            raise OAuthError("OAuth frontend components changed")
        runtime = context if context is not None else frontend
        return OAuthRuntimeView(
            frontend=frontend, session=runtime.session_manager.current, settings=frontend.settings,
            project_root=self._project_root, manager=runtime.mcp_manager, agent=resolve_active_agent(frontend),
            lifecycle=self, idle=not frontend_has_active_work(frontend, _oauth_owner=self),
            closed=self._closed or getattr(frontend, "_oauth", None) is not self,
        )

    def owns_network_task(self, frontend: Any, task: object) -> bool:
        """Exclude only this installed controller's exact owned reservation."""
        return (frontend is self._frontend and getattr(frontend, "_oauth", None) is self
                and task is self._network_task and task in self._tasks and not self._closed)

    def has_pending_actions(self) -> bool:
        return any(not task.done() for task in self._tasks)

    def defer_work_control(self, text: str) -> bool:
        """Require a fresh work-start control after the idle reservation ends."""
        from henchman.cli.workflow import command_starts_work

        if self._network_task is not None and not self._network_task.done() and command_starts_work(text):
            self._emit("MCP authentication is active; repeat this work-starting control after it finishes.")
            return True
        return False

    def submit(self, text: str) -> bool:
        """Capture fresh user intent synchronously, before scheduling its worker."""
        if not is_oauth_command(text):
            return False
        if self._closed:
            return True
        try:
            action, server = _parse(text)
        except ValueError:
            self._emit(OAUTH_COMMAND_GUIDANCE)
            return True
        network = action in {"login", "refresh", "connect"}
        if network and self._network_task is not None and not self._network_task.done():
            self._emit("Another MCP authentication action is active; cancel it or wait for it to finish.")
            return True
        try:
            view = self._view()
            metadata = view.project_root.stat()
            held = _ActionRuntime(view, (getattr(view.session, "id", None), getattr(view.session, "project_hash", None)),
                                  (metadata.st_dev, metadata.st_ino))
            ticket = self.controller.capture_user_intent(action, server)
        except Exception:
            self._emit("MCP authentication is unavailable for this runtime or server; network actions require idle work.")
            return True
        # No await between intent capture and reservation: a second UI event
        # cannot start an agent turn while the new action is awaiting admission.
        task = asyncio.create_task(self._execute(ticket, action, network), name="henchman-oauth-user-action")
        self._tasks[task] = held
        if network:
            self._network_task = task
            self._frontend._idle_control_task = task
        task.add_done_callback(self._finished)
        self._emit(f"MCP OAuth {action} requested.")
        return True

    def _finished(self, task: asyncio.Task[None]) -> None:
        # A task cancelled before its first instruction never enters _execute's
        # finally. Its done callback still owns and must release the reservation.
        if self._network_task is task:
            self._release(task, False)
        self._tasks.pop(task, None)
        if not task.cancelled():
            task.exception()

    def _release(self, task: asyncio.Task[None] | None, success: bool) -> None:
        held = self._tasks.get(task) if task is not None else None
        if getattr(self._frontend, "_idle_control_task", None) is task:
            self._frontend._idle_control_task = None
        if self._network_task is task:
            self._network_task = None
        if not self._closed and held is not None and self._same_runtime(held):
            try:
                self._settled(success)
            except Exception:
                self._emit("MCP authentication finished, but pending work could not be settled; inspect recovery before continuing.")

    def _same_runtime(self, held: _ActionRuntime) -> bool:
        """Stale completion must not hold or wake another session's queue."""
        try:
            current = self._view()
            metadata = current.project_root.stat()
            return (not current.closed and all(getattr(current, field) is getattr(held.view, field)
                    for field in ("frontend", "session", "settings", "manager", "agent", "lifecycle"))
                    and (getattr(current.session, "id", None), getattr(current.session, "project_hash", None)) == held.session_key
                    and Path.cwd().resolve() == held.view.project_root
                    and (metadata.st_dev, metadata.st_ino) == held.project_identity)
        except Exception:
            return False

    async def _execute(self, ticket: OAuthIntent, action: OAuthAction, network: bool) -> None:
        success = False
        try:
            result = await self.controller.execute(ticket)
            success = True
            if not self._closed:
                if result is None:
                    self._emit("MCP OAuth connection established; current tools are available.")
                else:
                    from henchman.cli.evidence import runtime_evidence_redactor

                    state = runtime_evidence_redactor(self._frontend).text(result.state)
                    self._emit(f"MCP OAuth {action}: {state}; refresh available: {result.refresh_available}.")
        except asyncio.CancelledError:
            if not self._closed:
                self._emit("MCP authentication cancelled; any external browser handoff may already have occurred.")
            raise
        except Exception:
            if not self._closed:
                self._emit("MCP authentication failed or its authority changed; no automatic retry. Use auth status to inspect.")
        finally:
            if network:
                self._release(asyncio.current_task(), success)

    def cancel(self) -> bool:
        """Request cancellation without releasing ownership before the join."""
        task = self._network_task
        if task is None or task.done():
            return False
        task.cancel("OAuth user action cancelled")
        return True

    async def aclose(self) -> None:
        """Revoke connection guards and join all owned actions before MCP teardown."""
        self._closed = True
        cancellation = None
        try:
            await self.controller.aclose()
        except asyncio.CancelledError as error:
            cancellation = error
        tasks = tuple(self._tasks)
        for task in tasks:
            if not task.done():
                task.cancel("OAuth frontend closed")
        joined = asyncio.gather(*tasks, return_exceptions=True)
        while not joined.done():
            try:
                await asyncio.shield(joined)
            except asyncio.CancelledError as error:
                cancellation = cancellation or error
        joined.result()
        if cancellation is not None:
            raise cancellation
