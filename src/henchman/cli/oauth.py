"""Runtime-only user intent for explicit OAuth actions; no frontend routing."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from time import monotonic
from typing import Literal, NoReturn, SupportsIndex
from weakref import WeakKeyDictionary

from henchman.cli.oauth_browser import open_oauth_browser
from henchman.config.schema import Settings
from henchman.core.session_helpers import compute_project_hash
from henchman.mcp.manager import McpManager
from henchman.mcp.oauth import OAuthError
from henchman.mcp.oauth_store import OAuthStatus

OAuthAction = Literal["status", "login", "refresh", "logout", "connect"]
GuardedBrowserOpener = Callable[[str, Callable[[], None]], Awaitable[None]]
INTENT_TTL_SECONDS = 60.0
MAX_PENDING_INTENTS = 32
_NETWORK_ACTIONS = {"login", "refresh", "connect"}


class _GuardCancellation(asyncio.CancelledError):
    """Bridge a synchronous guard to the action owner's cancellation checkpoint."""


async def _cancellation_checkpoint() -> None:
    task = asyncio.current_task()
    if task is not None and task.cancelling():
        await asyncio.sleep(0)
        raise asyncio.CancelledError("OAuth action was cancelled")


def _guard_cancellation(*, retained: bool) -> None:
    task = asyncio.current_task()
    if task is not None and task.cancelling():
        # Admission uses the public checkpoint to deliver the original reason.
        # A retained native guard can run on another owned task: preserve its
        # optional CPython message without depending on it for authority checks.
        message = getattr(task, "_cancel_message", None)
        args = () if message is None else (message,)
        if retained:
            raise asyncio.CancelledError(*args)
        raise _GuardCancellation(*args)


@dataclass(frozen=True, repr=False)
class OAuthRuntimeView:
    """Current trusted embedding identities, captured before asynchronous work.

    ``project_root`` is the startup project; ``idle`` excludes this controller's
    own action task but includes ordinary turns and background work. The frontend
    replaces ``lifecycle`` when its ownership ends. Nothing here is persisted.
    """

    frontend: object
    session: object | None
    settings: Settings
    project_root: Path
    manager: McpManager
    agent: object
    lifecycle: object
    idle: bool
    closed: bool = False


class OAuthIntent:
    """Opaque identity accepted only by its issuing controller, once."""

    __slots__ = ("__weakref__",)

    def __repr__(self) -> str:
        return "<OAuthIntent runtime-only>"

    def __reduce_ex__(self, _protocol: SupportsIndex) -> NoReturn:
        raise TypeError("OAuth intent cannot be copied or serialized")


@dataclass(frozen=True, repr=False)
class _Captured:
    action: OAuthAction
    server: str
    view: OAuthRuntimeView
    session_key: tuple[object, object] | None
    project: tuple[Path, int, int]
    configuration: object
    tools: object
    epoch: int
    manager_epoch: int
    connection_generation: int
    expires: float


async def _browser(url: str, authorize: Callable[[], None]) -> None:
    await open_oauth_browser(url, authorize=authorize)


def _session_key(session: object | None) -> tuple[object, object] | None:
    return None if session is None else (getattr(session, "id", None), getattr(session, "project_hash", None))


def _project(root: Path) -> tuple[Path, int, int]:
    path = root.resolve()
    if Path.cwd().resolve() != path or not path.is_dir():
        raise OAuthError("OAuth project authority changed")
    metadata = path.stat()
    return path, metadata.st_dev, metadata.st_ino


def _configuration(view: OAuthRuntimeView, server: str) -> object:
    config = view.settings.mcp_servers.get(server)
    return deepcopy(config.model_dump()) if config is not None else None


class OAuthController:
    """Issue intent only from a trusted frontend's actual user submission path.

    Model tools, imported commands and restored queues receive no controller or
    ticket. Python embedding code is trusted; a token string cannot substitute
    for the exact issued object. A successful connection keeps its runtime guard
    after the one-shot ticket is consumed, including during subsequent turns.
    """

    def __init__(self, current: Callable[[], OAuthRuntimeView], *,
                 browser_opener: GuardedBrowserOpener | None = None) -> None:
        self._current = current
        self._browser = browser_opener or _browser
        self._tickets: WeakKeyDictionary[OAuthIntent, _Captured] = WeakKeyDictionary()
        self._active: set[asyncio.Task[object]] = set()
        self._epoch = 0
        self._closed = False

    def has_active_action(self) -> bool:
        """Expose an owned network action to the frontend's turn-admission guard."""
        return bool(self._active)

    def _view(self) -> OAuthRuntimeView:
        view = self._current()
        if (type(view) is not OAuthRuntimeView or view.closed or self._closed
            or not isinstance(view.settings, Settings) or not isinstance(view.manager, McpManager)
            or view.frontend is None or view.agent is None or view.lifecycle is None
            or type(view.idle) is not bool):
            raise OAuthError("OAuth frontend authority is unavailable")
        runtime = view.manager._require_oauth_runtime()
        if not runtime.matches(view.settings, view.project_root):
            raise OAuthError("OAuth manager has another project or settings owner")
        if view.session is not None:
            key = _session_key(view.session)
            if key is None or not isinstance(key[0], str) or not key[0] or key[1] != compute_project_hash(view.project_root):
                raise OAuthError("OAuth session does not belong to the held project")
        return view

    def capture_user_intent(self, action: OAuthAction, server: str) -> OAuthIntent:
        """Synchronously capture one explicit user action; never accept raw URLs."""
        try:
            if (action not in {"status", "login", "refresh", "logout", "connect"}
                or not isinstance(server, str) or not server or len(server) > 256
                or any(ord(char) < 32 for char in server)):
                raise ValueError
            view = self._view()
            if (server not in view.settings.mcp_servers and server not in view.manager.configs
                and view.manager._require_oauth_runtime()._store.status(server).state == "missing"):
                raise OAuthError("OAuth action requires a configured or retained server identity")
            if action in _NETWORK_ACTIONS and (not view.idle or self._active):
                raise OAuthError("OAuth action requires an idle foreground runtime")
            for ticket, held in tuple(self._tickets.items()):
                if monotonic() >= held.expires:
                    del self._tickets[ticket]
            if len(self._tickets) >= MAX_PENDING_INTENTS:
                raise OAuthError("Too many pending OAuth actions")
            captured = _Captured(action, server, view, _session_key(view.session), _project(view.project_root),
                _configuration(view, server), deepcopy(view.settings.tools.model_dump()), self._epoch,
                view.manager._require_oauth_runtime()._http_epoch, view.manager._generations.get(server, 0),
                monotonic() + INTENT_TTL_SECONDS)
            ticket = OAuthIntent()
            self._tickets[ticket] = captured
            return ticket
        except Exception:
            raise OAuthError("OAuth user intent is invalid or its runtime is unavailable") from None

    def _check(self, captured: _Captured, *, idle: bool) -> None:
        try:
            view, original = self._view(), captured.view
            if (captured.epoch != self._epoch
                or view.manager._require_oauth_runtime()._http_epoch != captured.manager_epoch
                or any(getattr(view, field) is not getattr(original, field)
                       for field in ("frontend", "session", "settings", "manager", "agent", "lifecycle"))
                or _session_key(view.session) != captured.session_key
                or _project(view.project_root) != captured.project
                or _configuration(view, captured.server) != captured.configuration
                or (idle and (not view.idle or view.settings.tools.model_dump() != captured.tools))):
                raise ValueError
        except Exception:
            raise OAuthError("OAuth user or runtime authority changed") from None

    async def execute(self, ticket: OAuthIntent) -> OAuthStatus | None:
        """Consume exact intent before awaiting and retain no URL in runtime state."""
        captured = self._tickets.pop(ticket, None) if type(ticket) is OAuthIntent else None
        if captured is None or monotonic() >= captured.expires:
            raise OAuthError("OAuth intent is missing, stale or already consumed")
        await _cancellation_checkpoint()
        network = captured.action in _NETWORK_ACTIONS
        self._check(captured, idle=network)
        await _cancellation_checkpoint()
        if network and captured.view.manager._generations.get(captured.server, 0) != captured.connection_generation:
            raise OAuthError("OAuth connection authority changed since user intent was captured")
        if network and self._active:
            raise OAuthError("Another OAuth action is already active")
        task = asyncio.current_task()
        if task is None:
            raise OAuthError("OAuth action requires an owned asynchronous task")
        connected, failed = False, False
        established = None

        def authorize() -> None:
            if failed:
                raise OAuthError("OAuth action did not retain connection authority")
            self._check(captured, idle=network and not connected)
            _guard_cancellation(retained=connected)

        manager, server = captured.view.manager, captured.server
        if network:
            self._active.add(task)
        try:
            if captured.action == "status":
                result = manager.oauth_status(server, authorize=authorize)
            elif captured.action == "logout":
                result = manager.oauth_logout(server, authorize=authorize)
            elif captured.action == "login":
                result = await manager.oauth_login(server, authorize=authorize, guarded_browser_opener=self._browser)
            elif captured.action == "refresh":
                result = await manager.oauth_refresh(server, authorize=authorize)
            else:
                await manager.connect_oauth_server(server, authorize=authorize)
                established = manager.clients.get(server)
                result = None
            authorize()
            await _cancellation_checkpoint()
            connected = captured.action == "connect"
            return result
        except BaseException as primary:
            failed = True
            if isinstance(primary, _GuardCancellation):
                try:
                    await _cancellation_checkpoint()
                except asyncio.CancelledError as cancelled:
                    primary = cancelled
                else:
                    primary = asyncio.CancelledError(*primary.args)
            if established is not None and manager.clients.get(server) is established:
                try:
                    await manager.disconnect_server(server)
                except BaseException as cleanup:
                    if isinstance(cleanup, asyncio.CancelledError) and isinstance(primary, Exception):
                        primary = cleanup
                    primary.add_note("OAuth connection cleanup could not confirm remote closure.")
            raise primary
        finally:
            if network:
                self._active.discard(task)

    async def aclose(self) -> None:
        """Revoke retained authority and join active actions before frontend teardown."""
        self._closed = True
        self._epoch += 1
        self._tickets.clear()
        current = asyncio.current_task()
        tasks = tuple(task for task in self._active if task is not current)
        for task in tasks:
            task.cancel("OAuth frontend closed")
        joined = asyncio.gather(*tasks, return_exceptions=True)
        cancellation = None
        while not joined.done():
            try:
                await asyncio.shield(joined)
            except asyncio.CancelledError as error:
                cancellation = cancellation or error
        joined.result()
        if cancellation is not None:
            raise cancellation
