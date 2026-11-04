from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Final

from evals.helpers import EvalTestRig
from evals.models import EvalResult

# Import scenarios from the actual test modules
from evals.test_coding_tasks import (
    run_counter_refactor_scenario,
    run_fibonacci_scenario,
    run_fix_syntax_error_scenario,
)
from evals.test_edit_precision import (
    run_add_method_to_class_scenario,
    run_multi_file_edit_scenario,
    run_rename_variable_consistently_scenario,
)
from evals.test_package_lifecycle import run_package_lifecycle_scenario
from evals.test_python_reuse import run_python_reuse_scenario
from evals.test_test_docs import run_test_docs_scenario


@dataclass(frozen=True)
class CaseMetadata:
    id: str
    category: str
    seed: int
    fixture_identity: str
    oracle_identity: str
    profile: str
    version: Final[str] = "0.4.2-eval-v1"


# The typed registry
_REGISTRY: tuple[tuple[CaseMetadata, Callable[[EvalTestRig], Awaitable[EvalResult]]], ...] = (
    (
        CaseMetadata(
            id="counter-refactor",
            category="refactor",
            seed=42,
            fixture_identity="counter-refactor-fixture",
            oracle_identity="counter-refactor-oracle",
            profile="engineer",
        ),
        run_counter_refactor_scenario,
    ),
    (
        CaseMetadata(
            id="add-method-class",
            category="feature",
            seed=42,
            fixture_identity="add-method-class-fixture",
            oracle_identity="add-method-class-oracle",
            profile="engineer",
        ),
        run_add_method_to_class_scenario,
    ),
    (
        CaseMetadata(
            id="rename-variable",
            category="refactor",
            seed=42,
            fixture_identity="rename-variable-fixture",
            oracle_identity="rename-variable-oracle",
            profile="engineer",
        ),
        run_rename_variable_consistently_scenario,
    ),
    (
        CaseMetadata(
            id="multi-file-edit",
            category="multi-file",
            seed=42,
            fixture_identity="multi-file-edit-fixture",
            oracle_identity="multi-file-edit-oracle",
            profile="engineer",
        ),
        run_multi_file_edit_scenario,
    ),
    (
        CaseMetadata(
            id="python-reuse",
            category="reuse",
            seed=42,
            fixture_identity="python-reuse-fixture",
            oracle_identity="python-reuse-oracle",
            profile="engineer",
        ),
        run_python_reuse_scenario,
    ),
    (
        CaseMetadata(
            id="syntax-fix",
            category="bug-fix",
            seed=42,
            fixture_identity="syntax-fix-fixture",
            oracle_identity="syntax-fix-oracle",
            profile="engineer",
        ),
        run_fix_syntax_error_scenario,
    ),
    (
        CaseMetadata(
            id="fibonacci",
            category="feature",
            seed=42,
            fixture_identity="fibonacci-fixture",
            oracle_identity="fibonacci-oracle",
            profile="basic",
        ),
        run_fibonacci_scenario,
    ),
    (
        CaseMetadata(
            id="test-docs",
            category="test-docs",
            seed=42,
            fixture_identity="test-docs-fixture",
            oracle_identity="test-docs-oracle",
            profile="basic",
            version="0.4.2-eval-v1",
        ),
        run_test_docs_scenario,
    ),
    (
        CaseMetadata(
            id="package-lifecycle",
            category="package-lifecycle",
            seed=42,
            fixture_identity="package-lifecycle-fixture",
            oracle_identity="package-lifecycle-oracle",
            profile="team",
            version="0.4.2-eval-v1",
        ),
        run_package_lifecycle_scenario,
    ),
)


def get_case(case_id: str) -> tuple[CaseMetadata, Callable[[EvalTestRig], Awaitable[EvalResult]]]:
    """Lookup a case by its unique ID."""
    for metadata, callback in _REGISTRY:
        if metadata.id == case_id:
            return metadata, callback
    raise ValueError(f"Unknown case ID: {case_id}")


def list_cases() -> list[CaseMetadata]:
    """Returns a list of all registered cases."""
    return [metadata for metadata, _ in _REGISTRY]


async def dispatch_case(case_id: str, rig: EvalTestRig) -> EvalResult:
    """
    Dispatch a registered case to the rig and verify successful runtime.

    Args:
        case_id: The unique ID of the case to run.
        rig: The initialized EvalTestRig.

    Returns:
        The actual EvalResult from the callback.

    Raises:
        ValueError: If the case_id is not found in the registry.
    """
    metadata, callback = get_case(case_id)

    # Invoke the real callback
    result = await callback(rig)

    # Ensure the rig actually ran something
    rig.assert_successful_runs()

    return result
