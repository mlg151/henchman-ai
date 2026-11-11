"""Exercise the offline reuse oracle as a standalone isolated program."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def test_repository_reuse_oracle_refuses_unsafe_and_false_positive_candidates(tmp_path: Path) -> None:
    oracle = Path(__file__).resolve().parents[2] / "evals" / "repository_reuse_oracle_v1"
    environment = {
        "HOME": str(tmp_path),
        "USERPROFILE": str(tmp_path),
        "PATH": os.environ.get("PATH", ""),
        "SYSTEMROOT": os.environ.get("SYSTEMROOT", ""),
    }
    result = subprocess.run(
        [sys.executable, "-I", "-B", "-m", "unittest", "discover", "-s", str(oracle), "-p", "test_*.py", "-v"],
        cwd=tmp_path, env=environment, capture_output=True, text=True, timeout=30, check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
