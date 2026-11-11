"""Recoverable NTFS content restore using exclusive handles and absent-name renames."""

from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path
from uuid import uuid4

from henchman.advanced.checkpoint_models import CheckpointConflict, FileState
from henchman.advanced.checkpoint_windows import WindowsWorkspace


def _same(left: FileState, right: FileState) -> bool:
    return (left.status, left.content, left.mode) == (right.status, right.content, right.mode)


def restore_file(workspace: WindowsWorkspace, name: str, expected: FileState, desired: FileState,
                 directory: Path, index: int, fault: Callable[[str], None]) -> None:
    """Keep originals through retention; never replace a concurrently created name.

    Source ACL narrowing occurs before displacement and may survive interruption.
    Recover the prepared plan to complete its content decision. Arbitrary Windows
    ACLs, timestamps and extended metadata are not restored by this backend.
    """
    api = workspace.api
    backup, staged = directory / f"{index}.old", directory / f"{index}.new"
    with workspace.parent(name) as (target, parents), api.directories(directory):
        if parents != expected.parents:
            raise CheckpointConflict((name,), "Checkpoint parent directory changed")
        for partial in directory.glob(f"{index}.partial-*"):
            with api.open(partial, exclusive=True) as handle:
                api.check_file(handle)
                api.check_private(handle)
                api.delete(handle)
        if os.path.lexists(staged):
            with api.open(staged) as handle:
                api.check_private(handle)
                if not _same(workspace.read(handle), desired):
                    raise ValueError("Staged restore content or mode is corrupt; workspace left untouched")
        if expected.status == "text" and not os.path.lexists(backup):
            fault("before_displace")
            try:
                with api.open(target, exclusive=True, writable=True) as handle:
                    if not _same(workspace.read(handle), expected):
                        raise CheckpointConflict((name,))
                    # A protected directory alone is insufficient on Windows:
                    # traverse-bypass privilege can reach a publicly ACLed file.
                    api.make_private(handle)
                    fault("private_source")
                    api.rename(handle, backup)
                    fault("displaced")
            except OSError as error:
                raise CheckpointConflict((name,), "Windows checkpoint file is busy or unsupported; recover the prepared plan after resolving it") from error
        if os.path.lexists(backup):
            with api.open(backup) as handle:
                api.check_private(handle)
                if not _same(workspace.read(handle), expected):
                    raise CheckpointConflict((name,), "Retained original changed; recovery requires conflict resolution")
        current = workspace.state(name)
        if _same(current, desired) and current.parents == parents:
            return
        if current.status != "missing":
            raise CheckpointConflict((name,))
        if desired.status == "text":
            if desired.mode != 0o666:
                raise ValueError("Unsupported Windows checkpoint file mode")
            if not os.path.lexists(staged):
                temporary = directory / f"{index}.partial-{uuid4().hex}"
                with api.open(temporary, create=True, exclusive=True, writable=True) as handle:
                    api.write(handle, desired.content or b"")
                    api.rename(handle, staged)
                fault("staged")
            fault("before_publish")
            try:
                with api.open(staged, exclusive=True) as handle:
                    api.check_private(handle)
                    if not _same(workspace.read(handle), desired):
                        raise ValueError("Staged restore content or mode is corrupt; workspace left untouched")
                    api.rename(handle, target)
                    fault("linked")
            except OSError as error:
                raise CheckpointConflict((name,), "Windows checkpoint publication conflicted; current work and journal retained") from error
        fault("published")
        current = workspace.state(name)
        if not _same(current, desired) or current.parents != parents:
            raise CheckpointConflict((name,))
