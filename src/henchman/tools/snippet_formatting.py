"""Best-effort Black formatting of Python snippets without workspace discovery."""

from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

from henchman.tools.security import sanitize_error_message
from henchman.tools.subprocess_utils import run_bounded_subprocess

logger = logging.getLogger(__name__)

# Leave room for startup/cleanup within the half-second formatting budget.
SNIPPET_FORMAT_TIMEOUT = 0.3
MAX_SNIPPET_BYTES = 12 * 1024
_BLACK_SNIPPET_COMMAND = [
    sys.executable,
    "-I",
    "-c",
    "import black, sys\n"
    "source = sys.argv[1]\n"
    "try:\n"
    "    result = black.format_file_contents(source, fast=False, mode=black.Mode())\n"
    "except black.NothingChanged:\n"
    "    result = source\n"
    "sys.stdout.buffer.write(result.encode('utf-8'))\n",
]


async def format_python_snippet(code: str) -> str:
    """Format only an in-memory string, falling back without changing execution.

    The isolated worker calls Black's string API with defaults, never its CLI
    or project configuration discovery. Small argv/output limits bound work;
    larger snippets run unchanged. Process isolation lets a timeout terminate
    formatting rather than leave a Black thread consuming CPU in the CLI.
    Cancellation propagates after the shared subprocess helper reaps the worker.
    """
    try:
        if len(code) > MAX_SNIPPET_BYTES or len(code.encode("utf-8")) > MAX_SNIPPET_BYTES:
            raise ValueError(f"snippet exceeds {MAX_SNIPPET_BYTES}-byte formatting limit")
        async with asyncio.timeout(SNIPPET_FORMAT_TIMEOUT):
            result = await run_bounded_subprocess(
                [*_BLACK_SNIPPET_COMMAND, code],
                cwd=Path(sys.executable).parent,
                timeout=SNIPPET_FORMAT_TIMEOUT,
                max_output_bytes=MAX_SNIPPET_BYTES,
            )
        if result.returncode != 0:
            diagnostic = result.stderr.decode("utf-8", errors="replace")[-1000:]
            raise ValueError(f"Black exited {result.returncode}: {diagnostic}")
        if result.stdout_truncated or len(result.stdout) > MAX_SNIPPET_BYTES:
            raise ValueError(f"formatted snippet exceeds {MAX_SNIPPET_BYTES}-byte formatting limit")
        if not result.stdout:
            raise ValueError("Black returned incomplete snippet output")
        return result.stdout.decode("utf-8")
    except TimeoutError:
        logger.warning("Black snippet formatting timeout; executing original code")
    except Exception as exc:
        logger.warning(
            "Black snippet formatting failed (%s); executing original code",
            sanitize_error_message(exc),
        )
    return code
