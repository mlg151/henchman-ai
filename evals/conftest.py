"""Pytest configuration for behavioral evals."""

import os

import pytest


def pytest_configure(config: pytest.Config) -> None:
    """Register custom markers for evals."""
    config.addinivalue_line(
        "markers",
        "always_passes: marks test as expected to always pass (run in CI)",
    )
    config.addinivalue_line(
        "markers",
        "usually_passes: marks test as expected to usually pass (run nightly)",
    )


def pytest_collection_modifyitems(
    config: pytest.Config,
    items: list[pytest.Item],
) -> None:
    """Modify test collection based on environment."""
    run_all = os.environ.get("RUN_ALL_EVALS", "").lower() in ("1", "true", "yes")

    for item in items:
        # Add asyncio marker to all async tests
        if hasattr(item, "obj") and hasattr(item.obj, "__wrapped__"):
            # Check if it's an async function
            import asyncio

            if asyncio.iscoroutinefunction(item.obj.__wrapped__):
                item.add_marker(pytest.mark.asyncio)
