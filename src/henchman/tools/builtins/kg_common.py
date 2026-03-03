"""Shared utilities for knowledge graph tools.

Extracted to eliminate the duplicate ``_find_git_root`` function and the
identical ``__init__`` that previously existed in both ``kg_query.py``
and ``kg_update.py``.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

from henchman.tools.base import Tool

if TYPE_CHECKING:
    from henchman.knowledge.store import KnowledgeStore


def _find_git_root() -> Path | None:
    """Locate the git repository root from the current working directory."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0 and result.stdout.strip():
            return Path(result.stdout.strip())
    except (subprocess.SubprocessError, FileNotFoundError):
        pass
    return None


class KgToolBase(Tool):
    """Shared initialisation logic for knowledge graph tools.

    Both ``KgQueryTool`` and ``KgUpdateTool`` require identical lazy-init
    behaviour: accept an optional pre-built store, and defer discovery of
    the git root until the first query or update is made.  This base class
    provides that logic once.
    """

    def __init__(self: KgToolBase, store: KnowledgeStore | None = None) -> None:
        """Initialise the knowledge graph tool.

        Args:
            store: Optional pre-built store.  When ``None`` the tool
                will auto-discover the git root and create one on first use.
        """
        self._store = store
        self._initialised = store is not None
