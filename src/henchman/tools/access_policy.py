"""Restricted tool access through qualified implementations and directory handles.

This is a mediated filesystem boundary, not OS isolation. Unmediated tools are
denied whenever any restriction is active. Network restrictions currently deny
all network tools; they do not implement host filtering or isolate model traffic.
"""

from __future__ import annotations

import os
import stat
import weakref
from collections.abc import Iterator
from contextlib import contextmanager, suppress
from contextvars import ContextVar
from dataclasses import dataclass, field
from pathlib import Path
from typing import IO, TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from henchman.config.schema import ToolSettings
    from henchman.tools.base import Tool

_SAFE_DIRECTORY_OPS = (
    os.open in os.supports_dir_fd and os.mkdir in os.supports_dir_fd
    and os.stat in os.supports_dir_fd and os.stat in os.supports_follow_symlinks
    and hasattr(os, "O_NOFOLLOW") and hasattr(os, "O_DIRECTORY")
)


class ToolAccessError(PermissionError):
    """An invocation cannot uphold the configured restricted tool policy."""


def validate_tool_backend(settings: ToolSettings) -> None:
    """Refuse a requested execution backend that this runtime cannot enforce."""
    if settings.sandbox != "none":
        raise ToolAccessError(
            f"tools.sandbox={settings.sandbox} is unsupported: this runtime provides no enforced sandbox backend. "
            "Use a separately isolated runtime, or explicitly select tools.sandbox=none."
        )


@dataclass(frozen=True)
class _Directory:
    declared: Path
    resolved: Path
    device: int
    inode: int
    descriptor: int | None = field(default=None, repr=False, compare=False)

    @classmethod
    def bind(cls, path: Path) -> _Directory:
        declared = path.absolute()
        resolved = declared.resolve(strict=True)
        info = resolved.stat()
        if not stat.S_ISDIR(info.st_mode):
            raise ToolAccessError(f"Restricted filesystem root is not a directory: {path}")
        descriptor = None
        if _SAFE_DIRECTORY_OPS:
            descriptor = os.open(resolved, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            opened = os.fstat(descriptor)
            if (opened.st_dev, opened.st_ino) != (info.st_dev, info.st_ino):
                os.close(descriptor)
                raise ToolAccessError("Restricted filesystem root changed while binding")
        bound = cls(declared, resolved, info.st_dev, info.st_ino, descriptor)
        if descriptor is not None:
            # Holding the root prevents its inode from being reused while this
            # immutable policy (or an in-flight authorization) remains alive.
            weakref.finalize(bound, os.close, descriptor)
        return bound

    def check(self) -> None:
        if self.declared.resolve(strict=True) != self.resolved:
            raise ToolAccessError("Restricted filesystem root changed; rebind the project policy")
        info = self.resolved.stat()
        if not stat.S_ISDIR(info.st_mode) or (info.st_dev, info.st_ino) != (self.device, self.inode):
            raise ToolAccessError("Restricted filesystem root identity changed; rebind the project policy")


def _git_identity(project: Path) -> tuple[object, ...] | None:
    """Notice repository/worktree replacement without treating commits as resets."""
    entry = project / ".git"
    try:
        info = entry.lstat()
    except FileNotFoundError:
        return None
    if stat.S_ISDIR(info.st_mode):
        return info.st_dev, info.st_ino
    if not stat.S_ISREG(info.st_mode) or info.st_size > 4096:
        raise ToolAccessError("Unsupported project identity file under restricted policy")
    return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns


@dataclass(frozen=True)
class ToolAccessPolicy:
    """Immutable physical roots bound by trusted runtime configuration.

    None leaves that filesystem operation unrestricted; an empty tuple denies
    it. Separate registry ancestors retain separate checks, so a child policy
    can narrow access but cannot grant access excluded by its parent.
    """

    project: _Directory | None = None
    project_identity: tuple[object, ...] | None = None
    read_roots: tuple[_Directory, ...] | None = None
    write_roots: tuple[_Directory, ...] | None = None
    network_access: Literal["unrestricted", "disabled"] = "unrestricted"

    @property
    def restricted(self) -> bool:
        """Whether any operation is subject to explicit restrictions."""
        return self.read_roots is not None or self.write_roots is not None or self.network_access == "disabled"

    @classmethod
    def unbound(cls) -> ToolAccessPolicy:
        """Deny dispatch until a restricted manager receives its project root."""
        return cls(read_roots=(), write_roots=(), network_access="disabled")

    @classmethod
    def from_settings(cls, settings: ToolSettings, *, project_root: Path) -> ToolAccessPolicy:
        """Resolve configured roots once against the actual runtime project."""
        validate_tool_backend(settings)
        if (settings.filesystem_read_roots is None and settings.filesystem_write_roots is None
            and settings.network_access == "unrestricted"):
            return cls()
        project = _Directory.bind(project_root)

        def bind(roots: list[str] | None) -> tuple[_Directory, ...] | None:
            if roots is None:
                return None
            paths = [Path(root).expanduser() for root in roots]
            return tuple(_Directory.bind(path if path.is_absolute() else project.resolved / path) for path in paths)

        return cls(project, _git_identity(project.resolved), bind(settings.filesystem_read_roots),
                   bind(settings.filesystem_write_roots), settings.network_access)

    def check_project(self) -> None:
        """Reject project replacement rather than silently following a new root."""
        if self.project is None:
            raise ToolAccessError("Restricted tool policy requires a bound runtime project")
        self.project.check()
        if _git_identity(self.project.resolved) != self.project_identity:
            raise ToolAccessError("Restricted project/worktree identity changed; rebind the project policy")

    def matching_root(self, target: Path, *, write: bool) -> _Directory | None:
        """Validate one physical target and return a permitted directory handle root."""
        self.check_project()
        roots = self.write_roots if write else self.read_roots
        if roots is None:
            return None
        for root in roots:
            root.check()
            if target.is_relative_to(root.resolved) and target != root.resolved:
                return root
        operation = "write" if write else "read"
        raise ToolAccessError(f"Restricted filesystem policy denies {operation} target: {target}")


_POLICIES: ContextVar[tuple[ToolAccessPolicy, ...]] = ContextVar("henchman_tool_access_policies", default=())


def current_access_policies() -> tuple[ToolAccessPolicy, ...]:
    """Return immutable restrictions captured by the active registry dispatch."""
    return _POLICIES.get()


@contextmanager
def use_access_policies(policies: tuple[ToolAccessPolicy, ...]) -> Iterator[None]:
    """Bind restrictions to this operation and its child tasks without widening."""
    token = _POLICIES.set((*current_access_policies(), *policies))
    try:
        yield
    finally:
        _POLICIES.reset(token)


def _target(path: str) -> Path:
    if not path or "\0" in path or ".." in Path(path).parts:
        raise ToolAccessError("Restricted filesystem policy requires a valid non-traversing path")
    return Path(path).expanduser().resolve()


def validate_tool_access(tool: Tool, params: dict[str, object], policies: tuple[ToolAccessPolicy, ...]) -> None:
    """Fail closed unless this exact implementation has operation-time mediation."""
    if not policies:
        return
    from henchman.tools.builtins.file_read import ReadFileTool
    from henchman.tools.builtins.file_write import WriteFileTool

    if type(tool) not in (ReadFileTool, WriteFileTool):
        raise ToolAccessError(f"Tool '{tool.name}' is unsupported under restricted filesystem/network policy")
    if getattr(tool.execute, "__func__", None) is not type(tool).execute:
        raise ToolAccessError(f"Tool '{tool.name}' has an unsupported implementation under restricted policy")
    if not _SAFE_DIRECTORY_OPS:
        raise ToolAccessError("Restricted filesystem operations are unsupported on this platform")
    path = params.get("path")
    if not isinstance(path, str):
        raise ToolAccessError("Restricted filesystem policy requires a string path")
    target = _target(path)
    for policy in policies:
        policy.matching_root(target, write=type(tool) is WriteFileTool)


@contextmanager
def open_restricted_file(path: str, *, write: bool) -> Iterator[IO[str]]:
    """Open a regular, singly-linked file beneath checked directory descriptors.

    No await occurs between target selection, policy validation and opening.
    Symlinks inserted after resolution are rejected by O_NOFOLLOW. Existing
    files are not truncated until their descriptor type/link count is checked.
    Platforms without these primitives are explicitly unsupported.
    """
    policies = current_access_policies()
    if not policies or not _SAFE_DIRECTORY_OPS:
        raise ToolAccessError("Restricted filesystem operation lacks supported mediation")
    target = _target(path)
    roots = [policy.matching_root(target, write=write) for policy in policies]
    candidates = [root for root in roots if root is not None]
    root = max(candidates, key=lambda item: len(item.resolved.parts)) if candidates else _Directory.bind(Path(target.anchor))
    root.check()
    parts = target.relative_to(root.resolved).parts
    if not parts:
        raise ToolAccessError("Restricted filesystem target must be a regular file")
    directory_flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    if root.descriptor is None:
        raise ToolAccessError("Restricted filesystem root lacks supported directory mediation")
    directory = os.dup(root.descriptor)
    descriptor: int | None = None
    try:
        info = os.fstat(directory)
        if (info.st_dev, info.st_ino) != (root.device, root.inode):
            raise ToolAccessError("Restricted filesystem root changed while opening")
        for part in parts[:-1]:
            if write:
                with suppress(FileExistsError):
                    os.mkdir(part, dir_fd=directory)
            child = os.open(part, directory_flags, dir_fd=directory)
            os.close(directory)
            directory = child
        flags = (os.O_WRONLY | os.O_CREAT if write else os.O_RDONLY) | os.O_NOFOLLOW | os.O_NONBLOCK
        descriptor = os.open(parts[-1], flags, 0o666, dir_fd=directory)
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise ToolAccessError("Restricted filesystem target must be a regular file with no hardlink aliases")
        for policy in policies:
            policy.matching_root(target, write=write)
        if write:
            os.ftruncate(descriptor, 0)
        handle = os.fdopen(descriptor, "w" if write else "r", encoding="utf-8", newline="" if write else None)
        descriptor = None
        with handle:
            yield handle
    finally:
        if descriptor is not None:
            os.close(descriptor)
        os.close(directory)
