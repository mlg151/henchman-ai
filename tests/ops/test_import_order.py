"""Infrastructure and workflow imports must work in a fresh interpreter."""

import subprocess
import sys

import pytest


@pytest.mark.parametrize("first", ["workflow", "updater"])
def test_workflow_and_public_updater_import_in_either_order(first: str) -> None:
    statements = {
        "workflow": "from henchman.core.session_workflow import SessionWorkflow",
        "updater": "from henchman.ops import AutoUpdater",
    }
    second = "updater" if first == "workflow" else "workflow"
    script = (
        f"{statements[first]}; {statements[second]}; import henchman.ops; "
        "from henchman.ops.updater import AutoUpdater as ActualUpdater; "
        "assert 'AutoUpdater' in dir(henchman.ops); "
        "assert henchman.ops.AutoUpdater is ActualUpdater; "
        "assert not hasattr(henchman.ops, 'missing_export')"
    )
    result = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, timeout=30, check=False)
    assert result.returncode == 0, result.stderr
