"""Standard-library bootstrap: isolate opt-in protocol FDs before CLI imports."""

from __future__ import annotations

import io
import os
import stat
import sys
from dataclasses import dataclass


@dataclass
class ProtocolPipes:
    """Private, non-inheritable pipe descriptors owned by this process."""

    input_fd: int
    output_fd: int

    def close(self) -> None:
        for name in ("input_fd", "output_fd"):
            fd = getattr(self, name)
            if fd >= 0:
                setattr(self, name, -1)
                os.close(fd)


_pipes: ProtocolPipes | None = None


def protocol_pipes() -> ProtocolPipes:
    """Require the early bootstrap; embedded Click callers cannot adopt stdio."""
    if _pipes is None:
        raise RuntimeError("Use the installed headless entrypoint with POSIX pipes.")
    return _pipes


def _capture() -> ProtocolPipes:
    if os.name != "posix":
        raise RuntimeError("Headless protocol stdio currently requires POSIX pipes.")
    for fd in (0, 1):
        mode = os.fstat(fd).st_mode
        if not (stat.S_ISFIFO(mode) or stat.S_ISSOCK(mode)):
            raise RuntimeError("Headless protocol requires piped stdin and stdout; TTYs and files are unsupported.")
    input_fd = os.dup(0)
    try:
        output_fd = os.dup(1)
    except BaseException:
        os.close(input_fd)
        raise
    pipes = ProtocolPipes(input_fd, output_fd)
    try:
        os.set_inheritable(input_fd, False)
        os.set_inheritable(output_fd, False)
        # Isolate both Python streams and native/plugin fd access. Deliberately
        # do not restore stdout at exit: late destructors must remain diagnostic.
        null_fd = os.open(os.devnull, os.O_RDONLY)
        try:
            os.dup2(null_fd, 0)
        finally:
            os.close(null_fd)
        os.dup2(2, 1)
        sys.stdin = io.StringIO("")
        sys.stdout = sys.stderr
    except BaseException:
        pipes.close()
        raise
    return pipes


def main() -> None:
    """Route explicit protocol startup; preserve all legacy CLI arguments."""
    global _pipes
    protocol = len(sys.argv) > 1 and sys.argv[1] == "headless"
    help_only = any(arg in {"-h", "--help"} for arg in sys.argv[2:])
    if protocol and not help_only:
        try:
            _pipes = _capture()
        except (OSError, RuntimeError) as error:
            print(str(error) if isinstance(error, RuntimeError) else "Unable to isolate protocol pipes.", file=sys.stderr)
            raise SystemExit(2) from None
    try:
        from henchman.cli.app import cli
        from henchman.cli.app import main as cli_main

        if protocol and not help_only:
            import click

            try:
                # The explicit command needs no legacy argv normalization.
                # Click's default error rendering includes rejected values.
                cli(standalone_mode=False)
            except click.ClickException as error:
                print("Invalid headless arguments. Use 'henchman headless --help' for supported options.",
                      file=sys.stderr)
                raise SystemExit(error.exit_code) from None
            except click.Abort:
                print("Headless startup interrupted.", file=sys.stderr)
                raise SystemExit(130) from None
        else:
            cli_main()
    finally:
        if _pipes is not None:
            _pipes.close()
            _pipes = None
