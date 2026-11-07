import pytest
from evals.helpers import EvalTestRig, MockProvider
from evals.release_corpus import dispatch_case, get_case, list_cases
from evals.test_coding_tasks import run_fibonacci_scenario, run_fix_syntax_error_scenario
from evals.test_edit_precision import run_semantic_bug_fix_scenario
from evals.test_interruption_recovery import (
    REPAIRED_SOURCE,
    run_interruption_recovery_scenario,
)
from evals.test_package_lifecycle import run_package_lifecycle_scenario
from evals.test_test_docs import run_test_docs_scenario
from evals.test_tool_failure_recovery import run_tool_failure_recovery_scenario
from tests.testing.test_counter_eval_contract import (
    _GLOBAL_COUNTER,
    _INSTANCE_COUNTER,
    _write_counter,
)

from henchman.core.agent_config import AgentConfig
from henchman.providers.base import ToolCall


@pytest.mark.asyncio
async def test_registry_dispatch_counter_success():
    """Prove registry dispatch using the REGISTERED counter case."""
    provider = _write_counter(_INSTANCE_COUNTER)
    rig = EvalTestRig(provider=provider)

    try:
        rig.setup("counter-success")
        result = await dispatch_case("counter-refactor", rig)

        assert result.success
        assert any(log.tool_name == "write_file" and log.success for log in result.tool_logs)
    finally:
        rig.cleanup()


@pytest.mark.asyncio
async def test_registry_dispatch_counter_wrong_patch():
    """_write_counter(_GLOBAL_COUNTER) gives an independently wrong patch."""
    provider = _write_counter(_GLOBAL_COUNTER)
    rig = EvalTestRig(provider=provider)

    try:
        rig.setup("counter-wrong-patch")
        with pytest.raises(AssertionError):
            await dispatch_case("counter-refactor", rig)
    finally:
        rig.cleanup()


@pytest.mark.asyncio
async def test_registry_dispatch_counter_runtime_failure():
    """_write_counter(_INSTANCE_COUNTER, fail_after_write=True) writes correct code then fails runtime."""
    provider = _write_counter(_INSTANCE_COUNTER, fail_after_write=True)
    rig = EvalTestRig(provider=provider)

    try:
        rig.setup("counter-runtime-failure")
        with pytest.raises(AssertionError):
            await dispatch_case("counter-refactor", rig)
    finally:
        rig.cleanup()


@pytest.mark.asyncio
async def test_registry_metadata_uniqueness():
    """Test metadata uniqueness/known-id/unknown-id."""
    # Known IDs
    ids = [
        "counter-refactor",
        "add-method-class",
        "rename-variable",
        "multi-file-edit",
        "python-reuse",
        "syntax-fix",
        "fibonacci",
        "test-docs",
        "package-lifecycle",
        "semantic-bug-fix",
        "tool-failure-recovery",
        "interruption-recovery",
    ]

    for cid in ids:
        metadata, _ = get_case(cid)
        assert metadata.id == cid
        assert metadata.version == "0.4.2-eval-v1"
        assert metadata.seed == 42

    # Unknown ID
    with pytest.raises(ValueError, match="Unknown case ID: unknown-id"):
        get_case("unknown-id")


@pytest.mark.asyncio
async def test_list_cases_completeness():
    """Verify list_cases returns all registered cases with correct counts."""
    cases = list_cases()
    assert len(cases) == 12
    case_ids = {c.id for c in cases}
    expected_ids = {
        "counter-refactor",
        "add-method-class",
        "rename-variable",
        "multi-file-edit",
        "python-reuse",
        "syntax-fix",
        "fibonacci",
        "test-docs",
        "package-lifecycle",
        "semantic-bug-fix",
        "tool-failure-recovery",
        "interruption-recovery",
    }
    assert case_ids == expected_ids


def test_get_case_syntax_fix_metadata() -> None:
    """Verify metadata for the syntax-fix case."""
    metadata, callback = get_case("syntax-fix")
    assert metadata.id == "syntax-fix"
    assert metadata.category == "bug-fix"
    assert metadata.seed == 42
    assert metadata.fixture_identity == "syntax-fix-fixture"
    assert metadata.oracle_identity == "syntax-fix-oracle"
    assert metadata.profile == "engineer"
    assert callback is run_fix_syntax_error_scenario


def test_get_case_fibonacci_metadata() -> None:
    """Verify metadata for the fibonacci case."""
    metadata, callback = get_case("fibonacci")
    assert metadata.id == "fibonacci"
    assert metadata.category == "feature"
    assert metadata.seed == 42
    assert metadata.fixture_identity == "fibonacci-fixture"
    assert metadata.oracle_identity == "fibonacci-oracle"
    assert metadata.profile == "basic"
    assert metadata.version == "0.4.2-eval-v1"
    assert callback is run_fibonacci_scenario


def test_get_case_test_docs_metadata() -> None:
    """Verify metadata for the test-docs case."""
    metadata, callback = get_case("test-docs")
    assert metadata.id == "test-docs"
    assert metadata.category == "test-docs"
    assert metadata.seed == 42
    assert metadata.fixture_identity == "test-docs-fixture"
    assert metadata.oracle_identity == "test-docs-oracle"
    assert metadata.profile == "basic"
    assert metadata.version == "0.4.2-eval-v1"
    assert callback is run_test_docs_scenario


def test_get_case_package_lifecycle_metadata() -> None:
    """Verify metadata for the package-lifecycle case."""
    metadata, callback = get_case("package-lifecycle")
    assert metadata.id == "package-lifecycle"
    assert metadata.category == "package-lifecycle"
    assert metadata.seed == 42
    assert metadata.fixture_identity == "package-lifecycle-fixture"
    assert metadata.oracle_identity == "package-lifecycle-oracle"
    assert metadata.profile == "team"
    assert metadata.version == "0.4.2-eval-v1"
    assert callback is run_package_lifecycle_scenario


def test_get_case_semantic_bug_fix_metadata() -> None:
    """Verify metadata for the semantic-bug-fix case."""
    metadata, callback = get_case("semantic-bug-fix")
    assert metadata.id == "semantic-bug-fix"
    assert metadata.category == "bug-fix"
    assert metadata.seed == 42
    assert metadata.fixture_identity == "semantic-bug-fix-fixture"
    assert metadata.oracle_identity == "semantic-bug-fix-oracle"
    assert metadata.profile == "basic"
    assert metadata.version == "0.4.2-eval-v1"
    assert callback is run_semantic_bug_fix_scenario

def test_get_case_tool_failure_recovery_metadata() -> None:
    """Verify metadata for the tool-failure-recovery case."""
    metadata, callback = get_case("tool-failure-recovery")
    assert metadata.id == "tool-failure-recovery"
    assert metadata.category == "recovery"
    assert metadata.seed == 42
    assert metadata.fixture_identity == "tool-failure-recovery-fixture"
    assert metadata.oracle_identity == "tool-failure-recovery-oracle"
    assert metadata.profile == "engineer"
    assert metadata.version == "0.4.2-eval-v1"
    assert callback is run_tool_failure_recovery_scenario


def test_get_case_interruption_recovery_metadata() -> None:
    """Verify metadata for the interruption-recovery case."""
    metadata, callback = get_case("interruption-recovery")
    assert metadata.id == "interruption-recovery"
    assert metadata.category == "interruption-recovery"
    assert metadata.seed == 42
    assert metadata.fixture_identity == "interruption-recovery-fixture"
    assert metadata.oracle_identity == "interruption-recovery-oracle"
    assert metadata.profile == "engineer"
    assert metadata.version == "0.4.2-eval-v1"
    assert callback is run_interruption_recovery_scenario


@pytest.mark.asyncio
async def test_registry_dispatch_interruption_recovery_success():
    """Prove registry dispatch using the REGISTERED interruption case."""
    responses: list[str | list[ToolCall]] = [
        [ToolCall(id="t1-read", name="read_file", arguments={"path": "orders.py"})],
        [
            ToolCall(
                id="t1-ghost",
                name="write_file",
                arguments={"path": "orders.py", "content": REPAIRED_SOURCE},
            )
        ],
        [
            ToolCall(
                id="t2-write",
                name="write_file",
                arguments={"path": "orders.py", "content": REPAIRED_SOURCE},
            )
        ],
        "Resumed and fixed the module.",
    ]
    rig = EvalTestRig(
        MockProvider(responses), profile="engineer", config=AgentConfig(max_tokens=20000)
    )
    try:
        rig.setup("interruption-recovery-dispatch")
        result = await dispatch_case("interruption-recovery", rig)
        assert result.success
        assert rig.read_file("orders.py") == REPAIRED_SOURCE
    finally:
        rig.cleanup()


@pytest.mark.asyncio
async def test_registry_dispatch_interruption_recovery_wrong_recovery():
    """A recovery that leaves the oracle failing must reject through dispatch."""
    wrong = '"""Order pricing helpers."""\n\n\ndef order_total(prices):\n    return 0\n'
    responses: list[str | list[ToolCall]] = [
        [ToolCall(id="t1-read", name="read_file", arguments={"path": "orders.py"})],
        [
            ToolCall(
                id="t1-ghost",
                name="write_file",
                arguments={"path": "orders.py", "content": wrong},
            )
        ],
        [
            ToolCall(
                id="t2-write",
                name="write_file",
                arguments={"path": "orders.py", "content": wrong},
            )
        ],
        "Resumed and fixed the module.",
    ]
    rig = EvalTestRig(
        MockProvider(responses), profile="engineer", config=AgentConfig(max_tokens=20000)
    )
    try:
        rig.setup("interruption-recovery-dispatch-wrong")
        with pytest.raises(AssertionError):
            await dispatch_case("interruption-recovery", rig)
    finally:
        rig.cleanup()
