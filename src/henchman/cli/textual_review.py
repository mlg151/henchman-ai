"""Explicit bounded evidence review while a user decision remains pending."""

from __future__ import annotations

import asyncio
import contextlib
import json
import math
import os
import re
import stat
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from itertools import islice
from pathlib import Path
from typing import Any, ClassVar, cast
from uuid import uuid4

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Static, TextArea

from henchman.advanced.task_output import write_evidence
from henchman.cli.evidence import runtime_exception_text
from henchman.cli.textual_checkpoints import _joined
from henchman.cli.textual_context import _binding, _current_policy
from henchman.utils.evidence_redaction import (
    PRESERVE_IDENTITY,
    EvidenceRedactor,
)
from henchman.utils.exception_evidence import exception_text

MAX_SNAPSHOT_BYTES = 65536
MAX_TRANSCRIPT_ROWS = 64
MAX_REQUEST_BYTES = 32768
_OMITTED = "\n[Further evidence omitted by the review limit.]\n"


class _DisplayLimit(ValueError):
    pass


def request_evidence(request: Any, policy: EvidenceRedactor) -> dict[str, Any]:
    """Bound and detach JSON-like display data before redaction/serialization.

    On any omission discard the entire freeform request copy: a credential
    marker beyond the cutoff must not leave an earlier echo in the preview.
    Original executable arguments and approval keys remain untouched.
    """
    remaining, nodes = MAX_REQUEST_BYTES, 2048
    ancestors: set[int] = set()

    def detach(value: Any, depth: int = 0) -> Any:
        nonlocal remaining, nodes
        nodes -= 1
        if nodes < 0 or depth > 16:
            raise _DisplayLimit
        if isinstance(value, Path):
            value = str(value)
        if type(value) is str:
            if len(value) > remaining:
                raise _DisplayLimit
            remaining -= len(value.encode("utf-8"))
        elif value is None or type(value) is bool:
            remaining -= 8
        elif type(value) is int and value.bit_length() <= 256:
            remaining -= 80
        elif type(value) is float and math.isfinite(value):
            remaining -= 32
        elif type(value) in (dict, list, tuple):
            if id(value) in ancestors or len(value) > nodes:
                raise _DisplayLimit
            ancestors.add(id(value))
            try:
                if type(value) is dict:
                    if any(type(key) is not str for key in value):
                        raise _DisplayLimit
                    return {
                        detach(key, depth + 1): detach(item, depth + 1)
                        for key, item in value.items()
                    }
                return [detach(item, depth + 1) for item in value]
            finally:
                ancestors.remove(id(value))
        else:
            raise _DisplayLimit
        if remaining < 0:
            raise _DisplayLimit
        return value

    risk = request.risk_level if request.risk_level in ("low", "medium", "high") else "unknown"
    try:
        data = detach(
            {
                "tool_name": request.tool_name,
                "description": request.description,
                "params": request.params,
                "risk_level": request.risk_level,
            }
        )
    except (_DisplayLimit, UnicodeError):
        data = {
            "tool_name": "[Request details omitted]",
            "description": "Request omitted: display limit or unsupported value. Original arguments remain unchanged; deny if this is insufficient to decide.",
            "params": None,
            "risk_level": risk,
        }
    return cast(dict[str, Any], policy.redact(
        data,
        schema={
            "tool_name": None,
            "description": None,
            "params": None,
            "risk_level": PRESERVE_IDENTITY if risk != "unknown" else None,
        },
    ))


def _bounded(text: str, policy: EvidenceRedactor, limit: int) -> str:
    # Retain whole items only. A truncated unknown credential prefix could
    # otherwise survive when the complete value becomes known after capture.
    if len(text) > limit:
        return _OMITTED
    safe = policy.text(text)
    if len(safe.encode("utf-8", errors="replace")) > limit:
        return _OMITTED
    return safe


def _identity(app: Any) -> tuple[object, ...]:
    context = getattr(app, "core_context", None)
    fallback_root = Path.cwd().resolve() if getattr(context, "project_root", None) is None else None
    return _binding(app) + (
        id(getattr(app, "settings", None)),
        id(getattr(app, "provider", None)),
        fallback_root,
    )


def _transcript(app: Any, policy: EvidenceRedactor) -> str:
    """Read existing retained rows, without altering or duplicating runtime history."""
    from henchman.cli.textual_widgets import ChatPane, ToolMessage

    panes = app.screen_stack[0].query(ChatPane)
    if not panes:
        return "Retained transcript unavailable."
    pane = panes.first()
    pieces: list[str] = []
    remaining = 30000
    omitted = len(pane.children) > MAX_TRANSCRIPT_ROWS
    for child in islice(reversed(pane.children), MAX_TRANSCRIPT_ROWS):
        if isinstance(child, ToolMessage) and child.activity is not None:
            activity = child.activity
            labels = (activity.agent, activity.call, activity.name, activity.target)
            if any(label.endswith("…") for label in labels) or any(entry.clipped for entry in activity.entries):
                # Flattening would erase the truncation boundary needed for
                # later credential rotation. The live tool inspector retains
                # that typed boundary; this independent snapshot omits it.
                text = "[Already-clipped tool observation omitted from this snapshot; retained text cannot safely reconstruct its missing values.]"
            else:
                text = activity.evidence(policy)
        else:
            text = getattr(child, "_content_text", "")
        if not isinstance(text, str) or not text:
            continue
        if remaining < 256:
            omitted = True
            break
        piece = _bounded(text, policy, min(8192, remaining - 80))
        piece = f"\n--- {type(child).__name__} ---\n{piece}"
        remaining -= len(piece.encode())
        pieces.append(piece)
    return ("Earlier retained rows omitted.\n" if omitted else "") + "\n".join(reversed(pieces))


@dataclass(frozen=True)
class ReviewSnapshot:
    """A display copy is never an approval, execution argument or saved transcript."""

    text: str
    root: Path
    root_identity: tuple[int, int]


def _capture(origin: Any) -> ReviewSnapshot:
    app = origin.app
    policy = _current_policy(app)
    context = getattr(app, "core_context", None)
    root = Path(getattr(context, "project_root", None) or Path.cwd()).resolve()
    metadata = root.stat()
    request = getattr(origin, "_request", None)
    if request is not None:
        data = request_evidence(request, policy)
        params = json.dumps(data["params"], indent=2, ensure_ascii=False)
        decision = "Approval request\nTool: " + _bounded(data["tool_name"], policy, 1024)
        decision += "\nDescription: " + _bounded(data["description"], policy, 4096)
        decision += "\nParameters:\n" + _bounded(params, policy, 22000)
        decision += "\nEffective cwd and grant duration: not supplied by this request."
    else:
        decision = "Question\n" + _bounded(str(origin.question), policy, 26000)
    text = (
        "Read-only decision review\n"
        "Review, copy and export do not approve or answer this decision.\n"
        "Captured retained evidence; subsequent streaming is not included.\n\n"
        + decision
        + "\n\nRetained transcript context\n"
        + _transcript(app, policy)
    )
    return ReviewSnapshot(
        _bounded(text, policy, MAX_SNAPSHOT_BYTES), root, (metadata.st_dev, metadata.st_ino)
    )


def _directory_ok(path: Path) -> os.stat_result:
    info = path.lstat()
    if (
        not stat.S_ISDIR(info.st_mode)
        or getattr(info, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT
    ):
        raise OSError("Review export directories must be physical directories")
    return info


@contextlib.contextmanager
def _export_directory(snapshot: ReviewSnapshot) -> Iterator[tuple[Path, int | None]]:
    root = snapshot.root
    info = _directory_ok(root)
    if root.resolve() != root or (info.st_dev, info.st_ino) != snapshot.root_identity:
        raise OSError("Review project directory changed")
    directory = root / ".henchman" / "exports"
    if os.name == "posix":
        descriptor = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            info = os.fstat(descriptor)
            if (info.st_dev, info.st_ino) != snapshot.root_identity:
                raise OSError("Review project directory changed")
            for name in (".henchman", "exports"):
                with contextlib.suppress(FileExistsError):
                    os.mkdir(name, mode=0o700, dir_fd=descriptor)
                child = os.open(
                    name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=descriptor
                )
                os.close(descriptor)
                descriptor = child
            yield directory, descriptor
        finally:
            os.close(descriptor)
    else:
        # Match existing native evidence helpers: reject reparse paths before
        # use; Python on Windows cannot make a dir_fd-relative atomic open.
        for parent in (*reversed(root.parents), root):
            _directory_ok(parent)
        for parent in (directory.parent, directory):
            with contextlib.suppress(FileExistsError):
                parent.mkdir(mode=0o700)
            _directory_ok(parent)
        yield directory, None


def export_review(
    snapshot: ReviewSnapshot,
    text: str | Callable[[], str],
    format_name: str,
    valid: Callable[[], bool],
) -> Path:
    """Publish one private, exclusively named projected artifact; never overwrite."""

    def content() -> bytes:
        current = text() if callable(text) else text
        if format_name not in ("text", "markdown") or len(current.encode()) > MAX_SNAPSHOT_BYTES:
            raise ValueError("Unsupported review export or size")
        if format_name == "markdown":
            fence = "`" * (max((len(item) for item in re.findall(r"`+", current)), default=2) + 1)
            current = f"# Decision review\n\n{fence}text\n{current}\n{fence}\n"
        return current.encode("utf-8")

    def check_directory(directory: Path, descriptor: int | None) -> None:
        info = _directory_ok(snapshot.root)
        if (
            snapshot.root.resolve() != snapshot.root
            or (info.st_dev, info.st_ino) != snapshot.root_identity
        ):
            raise ValueError("Review project changed before export publication")
        _directory_ok(directory.parent)
        info = _directory_ok(directory)
        if descriptor is not None and not os.path.samestat(info, os.fstat(descriptor)):
            raise ValueError("Review export directory changed before publication")
        if not valid():
            raise ValueError("Decision or project changed before export publication")

    if not valid():
        raise ValueError("Decision or runtime changed; export was not started")
    content()  # Check format and bound before creating any export directories.
    with _export_directory(snapshot) as (directory, descriptor):
        name = "decision-" + uuid4().hex + (".txt" if format_name == "text" else ".md")
        temporary = "." + name + ".tmp"
        target: str | Path = name if descriptor is not None else directory / name
        source: str | Path = temporary if descriptor is not None else directory / temporary
        if not valid():
            raise ValueError("Decision or runtime changed; export was not started")
        output_fd = os.open(
            source,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
            0o600,
            dir_fd=descriptor,
        )
        primary: BaseException | None = None
        try:
            try:
                output = os.fdopen(output_fd, "wb", buffering=0)
            except BaseException:
                os.close(output_fd)
                raise
            with output:
                # Projection happens after directory/file open waits as well as
                # before publication; a repeatedly changing policy refuses.
                payload = content()
                write_evidence(output, payload)
                os.fsync(output.fileno())
                latest = content()
                if latest != payload:
                    output.seek(0)
                    output.truncate()
                    write_evidence(output, latest)
                    os.fsync(output.fileno())
                    if content() != latest:
                        raise ValueError("Credential projection kept changing; export unavailable")
                    payload = latest
                opened = os.fstat(output.fileno())
            check_directory(directory, descriptor)
            source_info = os.stat(source, dir_fd=descriptor, follow_symlinks=False)
            if (
                not stat.S_ISREG(source_info.st_mode)
                or source_info.st_nlink != 1
                or not os.path.samestat(opened, source_info)
            ):
                raise OSError("Review export temporary file changed")
            # link is exclusive (unlike replace/rename), publishing complete
            # bytes without overwriting a pre-existing artifact.
            os.link(
                source, target, src_dir_fd=descriptor, dst_dir_fd=descriptor, follow_symlinks=False
            )
            try:
                target_info = os.stat(target, dir_fd=descriptor, follow_symlinks=False)
                if not stat.S_ISREG(target_info.st_mode) or not os.path.samestat(
                    opened, target_info
                ):
                    raise OSError("Review export publication changed")
                check_directory(directory, descriptor)
                if content() != payload:
                    raise ValueError("Credential projection changed during export publication")
            except BaseException as error:
                try:
                    os.unlink(target, dir_fd=descriptor)
                except OSError:
                    error.add_note("Review published-file cleanup also failed")
                raise
        except BaseException as error:
            primary = error
            raise
        finally:
            try:
                with contextlib.suppress(FileNotFoundError):
                    os.unlink(source, dir_fd=descriptor)
            except OSError:
                if primary is None:
                    raise
                primary.add_note("Review temporary-file cleanup also failed")
    return directory / name


class ReviewTextArea(TextArea):
    """Refresh credential projection before the inherited keyboard copy action."""

    def action_copy(self) -> None:
        if isinstance(self.screen, DecisionReviewScreen):
            self.screen.copy_evidence(selection=True)


class DecisionReviewScreen(ModalScreen[None]):
    """Review is separate from the originating approval/question lifetime."""

    DEFAULT_CSS = """
    DecisionReviewScreen { background: $surface; }
    #review-dialog { width: 100%; height: 100%; padding: 0 1; }
    #review-title { height: 1; text-style: bold; }
    #review-status { height: 3; }
    #review-content { height: 1fr; }
    #review-actions { height: 3; }
    #review-actions Button { min-width: 8; width: 1fr; margin: 0; }
    #review-hint { height: 2; }
    """
    BINDINGS: ClassVar[list[Binding | tuple[str, str] | tuple[str, str, str]]] = [
        Binding("escape", "back", "Back", priority=True),
        Binding("ctrl+enter", "retain_decision", "Read only", priority=True, show=False),
    ]

    def __init__(self, origin: Any, snapshot: ReviewSnapshot) -> None:
        super().__init__()
        self.origin, self.snapshot = origin, snapshot
        self.runtime = origin.app
        self._binding = _identity(self.runtime)
        self._policy = _current_policy(self.runtime)
        self._export_task: asyncio.Task[None] | None = None
        self._review_closing = False

    def _valid(self) -> bool:
        return (
            not self._review_closing
            and self.origin.is_mounted
            and not getattr(self.origin, "expired", False)
            and self.origin in self.runtime.screen_stack
            and _identity(self.runtime) == self._binding
        )

    def _text(self) -> str:
        self._policy.register_policy(_current_policy(self.runtime))
        return _bounded(self.snapshot.text, self._policy, MAX_SNAPSHOT_BYTES)

    def _error(self, error: BaseException) -> str:
        self._policy.register_policy(_current_policy(self.runtime))
        return exception_text(error, self._policy)

    def compose(self) -> ComposeResult:
        with Vertical(id="review-dialog"):
            yield Static("Pending decision · read-only review", markup=False, id="review-title")
            yield Static(
                "Inspecting does not answer. Copy requests clipboard transfer; export is the file fallback.",
                markup=False,
                id="review-status",
            )
            yield ReviewTextArea(self._text(), read_only=True, soft_wrap=True, id="review-content")
            with Horizontal(id="review-actions"):
                yield Button("Back", id="review-back")
                yield Button("Copy", id="review-copy")
                yield Button("TXT export", id="review-export-text")
                yield Button("MD export", id="review-export-markdown")
            yield Static(
                "Select text / Ctrl+C, or Copy all. Terminal clipboard support varies; use file export remotely.",
                markup=False,
                id="review-hint",
            )

    def on_mount(self) -> None:
        self.query_one(TextArea).focus()
        self.set_interval(0.5, self.refresh_evidence)

    def refresh_evidence(self) -> None:
        area = self.query_one(TextArea)
        text = self._text()
        if text != area.text:
            area.load_text(text)
        if not self._valid():
            self.query_one("#review-status", Static).update(
                "Decision or runtime changed. Close this snapshot; no answer was sent."
            )
        for name in ("review-copy", "review-export-text", "review-export-markdown"):
            self.query_one("#" + name, Button).disabled = not self._valid() or (
                self._export_task is not None and not self._export_task.done()
            )

    def copy_evidence(self, *, selection: bool = False) -> None:
        area = self.query_one(TextArea)
        before = area.text
        self.refresh_evidence()
        if not self._valid():
            return
        if selection and before != area.text:
            self.query_one("#review-status", Static).update(
                "Credential projection changed; select text again before copying."
            )
            return
        text = area.selected_text if selection else area.text
        if text:
            try:
                self.app.copy_to_clipboard(text)
            except Exception as error:
                self.query_one("#review-status", Static).update(self._error(error))
            else:
                self.query_one("#review-status", Static).update(
                    "Clipboard transfer requested; terminal confirmation is unavailable. Export a file if it did not arrive."
                )

    def _export(self, format_name: str) -> None:
        if not self._valid() or (self._export_task is not None and not self._export_task.done()):
            self.refresh_evidence()
            return

        async def owned() -> None:
            try:
                path = await _joined(
                    lambda: export_review(self.snapshot, self._text, format_name, self._valid)
                )
                self._policy.register_policy(_current_policy(self.runtime))
                self.query_one("#review-status", Static).update(
                    self._policy.text(f"Exported private review to {path}")
                )
            except asyncio.CancelledError:
                raise
            except Exception as error:
                self.query_one("#review-status", Static).update(self._error(error))
            finally:
                if self.is_mounted:
                    self.refresh_evidence()

        self._export_task = asyncio.create_task(owned())
        self._export_task.add_done_callback(
            lambda _task: self.refresh_evidence() if self.is_mounted else None
        )
        self.refresh_evidence()

    async def on_unmount(self) -> None:
        self._review_closing = True
        if self._export_task is not None and not self._export_task.done():
            self._export_task.cancel()
            # The child's intentional cancellation is cleanup state, not the
            # caller's primary control. Shield settlement so repeated caller
            # cancellations cannot replace that first exception or detach it.
            settled = asyncio.gather(self._export_task, return_exceptions=True)
            cancelled: asyncio.CancelledError | None = None
            while not settled.done():
                try:
                    await asyncio.shield(settled)
                except asyncio.CancelledError as error:
                    cancelled = cancelled or error
            settled.result()
            if cancelled is not None:
                raise cancelled

    async def action_back(self) -> None:
        await self.on_unmount()
        if self.is_mounted:
            self.dismiss(None)

    def action_retain_decision(self) -> None:
        self.query_one("#review-status", Static).update(
            "Read-only review. Back returns to the unanswered decision."
        )

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        event.stop()
        name = event.button.id
        if name == "review-back":
            await self.action_back()
        elif name == "review-copy":
            self.copy_evidence()
        elif name in ("review-export-text", "review-export-markdown"):
            self._export(name.removeprefix("review-export-"))


def open_decision_review(origin: Any) -> None:
    """Open only from the current live decision; never resolve its future."""
    if origin.app.screen is not origin or getattr(origin, "expired", False):
        return
    try:
        snapshot = _capture(origin)

        def returned(_result: None) -> None:
            if origin.app.screen is origin and not getattr(origin, "expired", False):
                if getattr(origin, "_request", None) is not None:
                    origin.query_one("#btn-no", Button).focus()
                else:
                    origin.query_one(Input).focus()

        origin.app.push_screen(DecisionReviewScreen(origin, snapshot), returned)
    except (OSError, ValueError, TypeError) as error:
        origin.app.notify(runtime_exception_text(origin.app, error), severity="error", markup=False)
