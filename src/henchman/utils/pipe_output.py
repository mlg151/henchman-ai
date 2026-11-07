"""Nonblocking anonymous-pipe reads without occupying executor workers."""

from __future__ import annotations

import os
import sys


def pipe_chunk(reader: int) -> bytes | None:
    """Read available bytes, return None while empty, or b'' at EOF.

    POSIX callers must first make the reader nonblocking. Windows anonymous
    pipes use PeekNamedPipe because Python 3.11 cannot set them nonblocking.
    Each descriptor must have exactly one reader.
    """
    if sys.platform == "win32":
        import ctypes
        import msvcrt
        from ctypes import wintypes

        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        peek = kernel.PeekNamedPipe
        peek.argtypes = [wintypes.HANDLE, wintypes.LPVOID, wintypes.DWORD,
                         ctypes.POINTER(wintypes.DWORD), ctypes.POINTER(wintypes.DWORD),
                         ctypes.POINTER(wintypes.DWORD)]
        peek.restype = wintypes.BOOL
        available = wintypes.DWORD()
        if not peek(msvcrt.get_osfhandle(reader), None, 0, None, ctypes.byref(available), None):
            error = ctypes.get_last_error()
            if error in (109, 232):
                return b""
            raise ctypes.WinError(error)
        return os.read(reader, min(available.value, 4096)) if available.value else None
    try:
        return os.read(reader, 4096)
    except BlockingIOError:
        return None
