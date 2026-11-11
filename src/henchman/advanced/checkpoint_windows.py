"""Win32 handle primitives for local NTFS content checkpoints.

Directory handles deny rename/deletion during each operation; exclusive restore
handles reject concurrent opens. This is not a POSIX dir_fd emulation or a
sandbox against the same account or an administrator. Only writable, ordinary,
unnamed-stream files are supported. Restores deliberately narrow ACLs to the
current user and SYSTEM, including before moving a displaced original.
"""

from __future__ import annotations

import ctypes as c
import re
import sys
from collections.abc import Iterator
from contextlib import ExitStack, contextmanager
from functools import lru_cache
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any, cast

from henchman.advanced.checkpoint_models import CheckpointConflict, FileState

_DWORD = c.c_uint32
_HANDLE = c.c_void_p
_POINTER = c.c_void_p
_READ = 0x80000000
_WRITE = 0x40000000
_DELETE = 0x10000
_READ_CONTROL = 0x20000
_WRITE_DAC = 0x40000
_REPARSE = 0x400
_DIRECTORY = 0x10
_ALLOWED_FILE_ATTRIBUTES = 0x80 | 0x20 | 0x2000  # normal, archive, not indexed


def _last_error() -> int:
    return int(cast(Any, c).get_last_error())


def _win_error(code: int) -> OSError:
    return cast(OSError, cast(Any, c).WinError(code))


class UnsupportedWindowsFile(OSError):
    """A filesystem object is outside the explicitly supported native subset."""


def validate_path(value: str) -> None:
    """Reject Win32 aliases, devices and named streams before filesystem access."""
    for part in PurePosixPath(value).parts:
        stem = part.split(".", 1)[0].rstrip(" ").upper()
        if (part in {".", ".."} or part.endswith((".", " "))
                or any(ord(char) < 32 or 0xD800 <= ord(char) <= 0xDFFF or char in '<>:"|?*\\' for char in part)
                or stem in {"CON", "PRN", "AUX", "NUL", "CONIN$", "CONOUT$"}
                or re.fullmatch(r"(?:COM|LPT)[0-9¹²³]", stem)):
            raise ValueError("Unsupported Windows checkpoint pathname")


class _FileTime(c.Structure):
    _fields_ = [("low", _DWORD), ("high", _DWORD)]


class _FileInfo(c.Structure):
    _fields_ = [("attributes", _DWORD), ("creation", _FileTime), ("access", _FileTime),
                ("write", _FileTime), ("volume", _DWORD), ("size_high", _DWORD),
                ("size_low", _DWORD), ("links", _DWORD), ("index_high", _DWORD), ("index_low", _DWORD)]

    @property
    def identity(self) -> tuple[int, int]:
        return int(self.volume), int(self.index_high << 32 | self.index_low)

    @property
    def size(self) -> int:
        return int(self.size_high << 32 | self.size_low)


class _SecurityAttributes(c.Structure):
    _fields_ = [("length", _DWORD), ("descriptor", _POINTER), ("inherit", c.c_int)]


class _RenameInfo(c.Structure):
    _fields_ = [("replace", _DWORD), ("root", _HANDLE), ("length", _DWORD), ("name", c.c_wchar * 1)]


class WindowsApi:
    """Small typed Win32 surface; constructed only on native Windows."""

    kernel: Any
    security: Any
    sid: str

    def __init__(self) -> None:
        if sys.platform != "win32":
            raise ValueError("Windows checkpoint backend requires native Windows")
        self.kernel = c.WinDLL("kernel32", use_last_error=True)
        self.security = c.WinDLL("advapi32", use_last_error=True)
        self._bind(self.kernel, "CreateFileW", [c.c_wchar_p, _DWORD, _DWORD, _POINTER, _DWORD, _DWORD, _HANDLE], _HANDLE)
        self._bind(self.kernel, "CloseHandle", [_HANDLE], c.c_int)
        self._bind(self.kernel, "GetFileInformationByHandle", [_HANDLE, _POINTER], c.c_int)
        self._bind(self.kernel, "GetFileInformationByHandleEx", [_HANDLE, c.c_int, _POINTER, _DWORD], c.c_int)
        self._bind(self.kernel, "SetFileInformationByHandle", [_HANDLE, c.c_int, _POINTER, _DWORD], c.c_int)
        self._bind(self.kernel, "GetVolumeInformationByHandleW", [_HANDLE, c.c_wchar_p, _DWORD, _POINTER, _POINTER, _POINTER, c.c_wchar_p, _DWORD], c.c_int)
        self._bind(self.kernel, "GetFinalPathNameByHandleW", [_HANDLE, c.c_wchar_p, _DWORD, _DWORD], _DWORD)
        self._bind(self.kernel, "GetDriveTypeW", [c.c_wchar_p], _DWORD)
        self._bind(self.kernel, "CreateDirectoryW", [c.c_wchar_p, _POINTER], c.c_int)
        self._bind(self.kernel, "ReadFile", [_HANDLE, _POINTER, _DWORD, _POINTER, _POINTER], c.c_int)
        self._bind(self.kernel, "WriteFile", [_HANDLE, _POINTER, _DWORD, _POINTER, _POINTER], c.c_int)
        self._bind(self.kernel, "SetFilePointerEx", [_HANDLE, c.c_int64, _POINTER, _DWORD], c.c_int)
        self._bind(self.kernel, "FlushFileBuffers", [_HANDLE], c.c_int)
        self._bind(self.kernel, "GetCurrentProcess", [], _HANDLE)
        self._bind(self.kernel, "LocalFree", [_POINTER], _POINTER)
        self._bind(self.security, "OpenProcessToken", [_HANDLE, _DWORD, _POINTER], c.c_int)
        self._bind(self.security, "GetTokenInformation", [_HANDLE, c.c_int, _POINTER, _DWORD, _POINTER], c.c_int)
        self._bind(self.security, "ConvertSidToStringSidW", [_POINTER, _POINTER], c.c_int)
        self._bind(self.security, "ConvertStringSecurityDescriptorToSecurityDescriptorW", [c.c_wchar_p, _DWORD, _POINTER, _POINTER], c.c_int)
        self._bind(self.security, "GetSecurityDescriptorDacl", [_POINTER, _POINTER, _POINTER, _POINTER], c.c_int)
        self._bind(self.security, "GetSecurityDescriptorControl", [_POINTER, _POINTER, _POINTER], c.c_int)
        self._bind(self.security, "GetSecurityInfo", [_HANDLE, c.c_int, _DWORD, _POINTER, _POINTER, _POINTER, _POINTER, _POINTER], _DWORD)
        self._bind(self.security, "SetSecurityInfo", [_HANDLE, c.c_int, _DWORD, _POINTER, _POINTER, _POINTER, _POINTER], _DWORD)
        self._bind(self.security, "GetAce", [_POINTER, _DWORD, _POINTER], c.c_int)
        self.sid = self._current_sid()

    @staticmethod
    def _bind(library: Any, name: str, args: list[Any], result: Any) -> None:
        function = getattr(library, name)
        function.argtypes, function.restype = args, result

    @staticmethod
    def _ok(result: Any) -> None:
        if not result:
            raise _win_error(_last_error())

    def _sid_string(self, sid: Any) -> str:
        value = c.c_wchar_p()
        self._ok(self.security.ConvertSidToStringSidW(sid, c.byref(value)))
        try:
            return value.value or ""
        finally:
            self.kernel.LocalFree(value)

    def _current_sid(self) -> str:
        token, size = _HANDLE(), _DWORD()
        self._ok(self.security.OpenProcessToken(self.kernel.GetCurrentProcess(), 0x8, c.byref(token)))
        try:
            self.security.GetTokenInformation(token, 1, None, 0, c.byref(size))
            buffer = c.create_string_buffer(size.value)
            self._ok(self.security.GetTokenInformation(token, 1, buffer, len(buffer), c.byref(size)))
            return self._sid_string(_POINTER.from_buffer(buffer))
        finally:
            self.kernel.CloseHandle(token)

    @contextmanager
    def private_security(self) -> Iterator[_POINTER]:
        descriptor = _POINTER()
        sddl = f"D:P(A;OICI;FA;;;{self.sid})(A;OICI;FA;;;SY)"
        self._ok(self.security.ConvertStringSecurityDescriptorToSecurityDescriptorW(sddl, 1, c.byref(descriptor), None))
        try:
            yield descriptor
        finally:
            self.kernel.LocalFree(descriptor)

    @contextmanager
    def open(self, path: Path, *, directory: bool = False, exclusive: bool = False,
             create: bool = False, writable: bool = False, share: int | None = None,
             attributes_only: bool = False) -> Iterator[int]:
        access = _READ_CONTROL | (0x80 if attributes_only or directory else _READ)
        if directory:
            # Attribute-only handles do not participate in Win32 sharing
            # enforcement. FILE_LIST_DIRECTORY (FILE_READ_DATA) makes denial
            # of FILE_SHARE_DELETE effective for these held ancestors.
            access |= 0x1
        if exclusive:
            access |= _DELETE | _WRITE_DAC
        if writable:
            access |= _WRITE
        # Directory writes must remain shareable: replacing a child opens its
        # parent for write access. Withhold DELETE to pin the directory itself.
        default_share = 0 if exclusive else (3 if directory else 1)
        sharing = share if share is not None else default_share
        # OPEN_REPARSE_POINT operates on the final object, never its target.
        flags = 0x00200000 | (0x02000000 if directory else 0)
        with self.private_security() as descriptor:
            security = _SecurityAttributes(c.sizeof(_SecurityAttributes), descriptor, False)
            handle = self.kernel.CreateFileW(str(path), access, sharing, c.byref(security) if create else None,
                                             1 if create else 3, flags, None)
            error = _last_error()
        if handle == c.c_void_p(-1).value:
            raise _win_error(error)
        try:
            info = self.info(handle)
            if info.attributes & _REPARSE or bool(info.attributes & _DIRECTORY) != directory:
                raise UnsupportedWindowsFile("Reparse points and unsupported object types are not checkpoint files")
            if not directory and info.links != 1:
                raise UnsupportedWindowsFile("Checkpoint files must have exactly one link")
            self.check_name(handle, path)
            yield handle
        finally:
            self.kernel.CloseHandle(handle)

    def info(self, handle: int) -> _FileInfo:
        info = _FileInfo()
        self._ok(self.kernel.GetFileInformationByHandle(handle, c.byref(info)))
        return info

    def check_name(self, handle: int, path: Path) -> None:
        buffer = c.create_unicode_buffer(32768)
        length = self.kernel.GetFinalPathNameByHandleW(handle, buffer, len(buffer), 0)
        self._ok(length)
        if length >= len(buffer):
            raise UnsupportedWindowsFile("Checkpoint pathname exceeds native limits")
        value = buffer.value
        if value.startswith("\\\\?\\"):
            value = value[4:]
        if PureWindowsPath(value) != PureWindowsPath(path):
            raise UnsupportedWindowsFile("Windows short-name aliases are unsupported checkpoint paths")

    def check_volume(self, handle: int, path: Path) -> None:
        name, flags = c.create_unicode_buffer(32), _DWORD()
        self._ok(self.kernel.GetVolumeInformationByHandleW(handle, None, 0, None, None, c.byref(flags), name, len(name)))
        if name.value != "NTFS" or not flags.value & 8 or self.kernel.GetDriveTypeW(path.anchor) != 3:
            raise ValueError("Windows checkpoints require a local fixed NTFS volume")

    def check_directory(self, handle: int) -> None:
        info = _DWORD()
        if self.kernel.GetFileInformationByHandleEx(handle, 23, c.byref(info), c.sizeof(info)):
            if info.value:
                raise UnsupportedWindowsFile("Case-sensitive Windows checkpoint directories are unsupported")
        elif _last_error() not in {1, 50, 87}:  # Older supported Windows: no case-sensitive flag.
            raise _win_error(_last_error())

    def check_file(self, handle: int) -> None:
        info = self.info(handle)
        if info.links != 1 or info.attributes & ~_ALLOWED_FILE_ATTRIBUTES:
            raise UnsupportedWindowsFile("Only ordinary writable Windows checkpoint files are supported")
        buffer = c.create_string_buffer(65536)
        self._ok(self.kernel.GetFileInformationByHandleEx(handle, 7, buffer, len(buffer)))  # FileStreamInfo
        next_offset, length = _DWORD.from_buffer(buffer).value, _DWORD.from_buffer(buffer, 4).value
        if next_offset or length != 14 or buffer.raw[24:24 + length].decode("utf-16-le") != "::$DATA":
            raise UnsupportedWindowsFile("Alternate data streams are unsupported checkpoint content")

    def read(self, handle: int, limit: int) -> bytes:
        self._ok(self.kernel.SetFilePointerEx(handle, 0, None, 0))
        result = bytearray()
        while len(result) <= limit:
            buffer = c.create_string_buffer(min(65536, limit + 1 - len(result)))
            count = _DWORD()
            self._ok(self.kernel.ReadFile(handle, buffer, len(buffer), c.byref(count), None))
            if not count.value:
                break
            result.extend(buffer.raw[:count.value])
        return bytes(result)

    def write(self, handle: int, content: bytes) -> None:
        offset = 0
        while offset < len(content):
            data, count = content[offset:offset + 65536], _DWORD()
            self._ok(self.kernel.WriteFile(handle, data, len(data), c.byref(count), None))
            if not count.value:
                raise OSError("Windows checkpoint write made no progress")
            offset += count.value
        self._ok(self.kernel.FlushFileBuffers(handle))

    def rename(self, handle: int, target: Path) -> None:
        """Rename the held file only if destination is absent; never replace."""
        data = str(target).encode("utf-16-le")
        buffer = c.create_string_buffer(_RenameInfo.name.offset + len(data) + 2)
        header = _RenameInfo.from_buffer(buffer)
        header.replace, header.root, header.length = 0, None, len(data)
        c.memmove(c.addressof(buffer) + _RenameInfo.name.offset, data, len(data))
        self._ok(self.kernel.SetFileInformationByHandle(handle, 3, buffer, len(buffer)))

    def delete(self, handle: int) -> None:
        disposition = c.c_ubyte(1)
        self._ok(self.kernel.SetFileInformationByHandle(handle, 4, c.byref(disposition), c.sizeof(disposition)))

    def make_private(self, handle: int) -> None:
        with self.private_security() as descriptor:
            present, defaulted, acl = c.c_int(), c.c_int(), _POINTER()
            self._ok(self.security.GetSecurityDescriptorDacl(descriptor, c.byref(present), c.byref(acl), c.byref(defaulted)))
            error = self.security.SetSecurityInfo(handle, 1, 4 | 0x80000000, None, None, acl, None)
            if error:
                raise _win_error(error)
        self.check_private(handle)

    def check_private(self, handle: int, *, protected: bool = False) -> None:
        acl, descriptor = _POINTER(), _POINTER()
        error = self.security.GetSecurityInfo(handle, 1, 4, None, None, c.byref(acl), None, c.byref(descriptor))
        if error:
            raise _win_error(error)
        try:
            control, revision = c.c_uint16(), _DWORD()
            self._ok(self.security.GetSecurityDescriptorControl(descriptor, c.byref(control), c.byref(revision)))
            if not acl.value or (protected and not control.value & 0x1000):
                raise ValueError("Windows checkpoint storage must have a private protected DACL")
            count = c.c_uint16.from_address(acl.value + 4).value
            allowed = set()
            for index in range(count):
                ace = _POINTER()
                self._ok(self.security.GetAce(acl, index, c.byref(ace)))
                assert ace.value is not None
                if c.c_ubyte.from_address(ace.value).value != 0:
                    raise ValueError("Unsupported private checkpoint DACL")
                sid = self._sid_string(ace.value + 8)
                if sid not in {self.sid, "S-1-5-18"}:
                    raise ValueError("Windows checkpoint storage is not private to the current user and SYSTEM")
                allowed.add(sid)
            if self.sid not in allowed:
                raise ValueError("Windows checkpoint storage lacks its private owner grant")
        finally:
            self.kernel.LocalFree(descriptor)

    def private_directory(self, path: Path) -> None:
        with self.private_security() as descriptor:
            security = _SecurityAttributes(c.sizeof(_SecurityAttributes), descriptor, False)
            if not self.kernel.CreateDirectoryW(str(path), c.byref(security)) and _last_error() != 183:
                raise _win_error(_last_error())
        with self.open(path, directory=True) as handle:
            self.check_private(handle, protected=True)

    @contextmanager
    def directories(self, path: Path) -> Iterator[tuple[tuple[int, int], ...]]:
        """Pin every ancestor, rejecting junctions/mounts before walking deeper."""
        path = path.absolute()
        if len(path.drive) != 2 or path.drive[1] != ":":
            raise ValueError("Windows checkpoints require a local drive path")
        with ExitStack() as stack:
            identities: list[tuple[int, int]] = []
            for directory in (*reversed(path.parents), path):
                handle = stack.enter_context(self.open(directory, directory=True))
                self.check_directory(handle)
                identity = self.info(handle).identity
                if identities and identity[0] != identities[0][0]:
                    raise UnsupportedWindowsFile("Checkpoint paths across volumes are unsupported")
                identities.append(identity)
            self.check_volume(handle, path)
            yield tuple(identities)


@lru_cache(maxsize=1)
def windows_api() -> WindowsApi:
    return WindowsApi()


class WindowsWorkspace:
    def __init__(self, files: Any) -> None:
        self.files = files
        self.api = windows_api()
        with self.api.directories(files.root) as identities:
            files.identity = identities[-1]

    @contextmanager
    def parent(self, value: str) -> Iterator[tuple[Path, tuple[tuple[int, int], ...]]]:
        value = self.files.path(value)
        target = self.files.root / value
        with self.api.directories(target.parent) as identities:
            root_index = len(self.files.root.parents)
            parents = identities[root_index:]
            if not parents or parents[0] != self.files.identity:
                raise CheckpointConflict(reason="Checkpoint project directory changed")
            self.files.check_root()
            yield target, parents

    def state(self, value: str) -> FileState:
        try:
            with self.parent(value) as (path, parents):
                try:
                    with self.api.open(path) as handle:
                        return self.read(handle, parents)
                except FileNotFoundError:
                    return FileState("missing", parents=parents)
        except FileNotFoundError:
            return FileState("missing")
        except OSError:
            return FileState("unsupported")

    def read(self, handle: int, parents: tuple[tuple[int, int], ...] = ()) -> FileState:
        self.api.check_file(handle)
        info = self.api.info(handle)
        if info.size > self.files.max_file_bytes:
            return FileState("oversized")
        content = self.api.read(handle, self.files.max_file_bytes)
        self.api.check_file(handle)
        if len(content) > self.files.max_file_bytes:
            return FileState("oversized")
        try:
            text = content.decode("utf-8")
        except UnicodeError:
            return FileState("binary")
        if "\x00" in text:
            return FileState("binary")
        if self.files.redactor.text(text) != text:
            return FileState("secret")
        return FileState("text", content, 0o666, parents)
