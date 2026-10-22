"""Fixtures for issue tests."""
import pytest


@pytest.fixture(autouse=True)
def rig():
    """Set up a fresh eval rig for every issue test."""
    from evals.helpers import EvalTestRig

    rig = EvalTestRig()
    rig.setup("evals")
    try:
        yield rig
    finally:
        rig.cleanup()
