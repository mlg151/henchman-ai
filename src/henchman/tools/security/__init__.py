"""Security package for Henchman tools.

The security utilities live in the sibling ``security.py`` module.  That file
is shadowed by this package at the Python level, so this ``__init__.py``
re-exports everything from it via ``importlib`` so that all existing
``from henchman.tools.security import …`` call-sites continue to work
unchanged.

The shell-security tool (``SecureShellTool``, etc.) is **not** imported here
to avoid a circular-import chain with ``henchman.tools.builtins``.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

# ---------------------------------------------------------------------------
# Re-export security.py (which is shadowed at the Python package level)
# ---------------------------------------------------------------------------
_module_path = Path(__file__).parent.parent / "security.py"
_spec = importlib.util.spec_from_file_location("henchman.tools.security._impl", _module_path)
_mod = importlib.util.module_from_spec(_spec)  # type: ignore[arg-type]
_spec.loader.exec_module(_mod)  # type: ignore[union-attr]

for _name in dir(_mod):
    if not _name.startswith("_"):
        globals()[_name] = getattr(_mod, _name)

del _module_path, _spec, _mod, _name
