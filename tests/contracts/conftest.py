"""Shared fixtures for contract tests."""

from __future__ import annotations

import pytest

from henchman.testing.contract import ContractSuite


@pytest.fixture(scope="session")
def contract_suite() -> ContractSuite:
    """Provide the shared contract validator."""
    return ContractSuite()
