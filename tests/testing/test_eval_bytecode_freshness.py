import os
import py_compile
import sys
from pathlib import Path

import pytest
from evals.helpers import verify_python


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    return tmp_path


@pytest.mark.parametrize(
    "stale_value, current_value, should_reject",
    [
        ("PASS", "FAIL", True),  # stalePASS / currentFAIL -> must reject (see current FAIL)
        ("FAIL", "PASS", False),  # staleFAIL / currentPASS -> must accept (see current PASS)
    ],
)
async def test_eval_bytecode_freshness(
    workspace: Path, stale_value: str, current_value: str, should_reject: bool
) -> None:
    """Verify that verify_python correctly identifies fresh bytecode and ignores stale cache.

    This test creates a scenario where the source code has changed but the modification
    time remains the same, which should normally cause Python to use the stale
    __pycache__ if not for the pycache_prefix.
    """
    oracle_path = workspace / "oracle_target.py"

    # 1. Create initial source with equal-sized literals
    initial_content = f"VALUE = '{stale_value}'"
    oracle_path.write_text(initial_content, encoding="utf-8")

    # Capture original source stat
    initial_stat = oracle_path.stat()

    # 2. Compile with TIMESTAMP invalidation into the workspace
    # We temporarily unset sys.pycache_prefix to ensure it goes into the workspace's __pycache__
    old_prefix = sys.pycache_prefix
    try:
        sys.pycache_prefix = None
        py_compile.compile(
            str(oracle_path),
            doraise=True,
            invalidation_mode=py_compile.PycInvalidationMode.TIMESTAMP,
        )
    finally:
        sys.pycache_prefix = old_prefix

    # 3. Overwrite with opposite value and restore original mtime
    new_content = f"VALUE = '{current_value}'"
    oracle_path.write_text(new_content, encoding="utf-8")

    # Restore original mtime to keep it the same as the compiled version
    os.utime(oracle_path, ns=(initial_stat.st_atime_ns, initial_stat.st_mtime_ns))

    # Ensure all files are closed (write_text does this)

    code = "import oracle_target; assert oracle_target.VALUE == 'PASS'"

    if should_reject:
        # stalePASS / currentFAIL -> expect rejection (AssertionError)
        # If it sees current FAIL, it should raise AssertionError.
        with pytest.raises(AssertionError):
            await verify_python(workspace, code)
    else:
        # staleFAIL / currentPASS -> expect acceptance (no AssertionError)
        # If it sees current PASS, it should succeed.
        await verify_python(workspace, code)
