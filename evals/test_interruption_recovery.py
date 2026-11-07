"""Evaluate recovery after an observed bounded-turn interruption.

The first turn is bounded to a single tool round, so any first attempt that
acts on the workspace is interrupted before it can finish. The recovery turn
must resume from the persisted workspace, keep the provided tests untouched,
and make the independent pytest oracle pass.
"""

from evals.helpers import EvalTestRig, run_pytest_evidence
from evals.models import EvalResult

#: Broken fixture: forgets to round to cents, so the provided tests fail.
BROKEN_SOURCE: str = (
    '"""Order pricing helpers."""\n'
    "\n"
    "\n"
    "def order_total(prices):\n"
    "    return sum(prices)\n"
)

#: Repaired implementation the recovery turn must deliver.
REPAIRED_SOURCE: str = (
    '"""Order pricing helpers."""\n'
    "\n"
    "\n"
    "def order_total(prices):\n"
    "    return round(sum(prices), 2)\n"
)

#: Provided tests; independent oracle, must never be rewritten to pass.
TEST_SOURCE: str = (
    '"""Tests for order pricing helpers."""\n'
    "\n"
    "\n"
    "def test_empty_order_costs_nothing():\n"
    "    from orders import order_total\n"
    "\n"
    "    assert order_total([]) == 0.0\n"
    "\n"
    "\n"
    "def test_order_total_rounds_to_cents():\n"
    "    from orders import order_total\n"
    "\n"
    "    assert order_total([1.1, 2.2]) == 3.3\n"
    "    assert order_total([0.1, 0.2]) == 0.3\n"
)


async def run_interruption_recovery_scenario(rig: EvalTestRig) -> EvalResult:
    """Require an observed interrupted turn, then verified recovery of the task."""
    rig.create_file("orders.py", BROKEN_SOURCE)
    rig.create_file("test_orders.py", TEST_SOURCE)

    # Bounded to one tool round: any acting first attempt is interrupted.
    await rig.run(
        "orders.py is incomplete: order_total must round to the nearest cent. "
        "Make the provided tests in test_orders.py pass without modifying that "
        "file.",
        max_iterations=1,
    )
    rig.consume_expected_interruption()

    second = await rig.run(
        "You were interrupted mid-task and did not finish. Resume in the same "
        "workspace: fix orders.py so the provided tests in test_orders.py pass. "
        "Do not modify test_orders.py.",
    )
    assert second.success, second.error or second.final_response
    assert rig.read_file("test_orders.py") == TEST_SOURCE, (
        "provided tests were tampered with"
    )
    evidence = await run_pytest_evidence(rig.test_dir, "test_orders.py")
    assert evidence is not None, "Independent pytest evidence unavailable"
    assert evidence.exit_status == 0 and evidence.failed == 0, (
        f"Recovery left the provided tests failing "
        f"(executed={evidence.executed}, failed={evidence.failed})"
    )
    assert evidence.executed >= 2, (
        f"Expected the full provided test file to execute, ran {evidence.executed}"
    )
    assert rig.read_file("test_orders.py") == TEST_SOURCE, (
        "verification changed the provided tests"
    )
    return second
