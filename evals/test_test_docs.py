"""Independent test-quality checks for the planned test/documentation case."""

from pathlib import Path

from evals.helpers import EvalResult, EvalTestRig, run_pytest_evidence, verify_python

_CLAMP_SOURCE: str = """
def clamp(value: int, lower: int, upper: int) -> int:
    \"\"\"Clamp a value between lower and upper bounds.\"\"\"
    if lower > upper:
        raise ValueError("lower exceeds upper")
    return max(lower, min(value, upper))
"""

_CLAMP_MUTANTS: dict[str, str] = {
    "missing-lower": _CLAMP_SOURCE.replace(
        "return max(lower, min(value, upper))", "return min(value, upper)",
    ),
    "missing-upper": _CLAMP_SOURCE.replace(
        "return max(lower, min(value, upper))", "return max(lower, value)",
    ),
    "missing-range-error": _CLAMP_SOURCE.replace(
        '    if lower > upper:\n        raise ValueError("lower exceeds upper")\n', "",
    ),
    "equal-bounds-error": _CLAMP_SOURCE.replace("if lower > upper:", "if lower >= upper:"),
    "nonnegative-only": _CLAMP_SOURCE.replace(
        "return max(lower, min(value, upper))", "return max(0, max(lower, min(value, upper)))",
    ),
}


async def verify_clamp_tests(workspace: Path) -> None:
    """Require passing candidate tests and a real failure for every semantic mutant."""
    bounds_path = workspace / "bounds.py"
    test_bounds_path = workspace / "test_bounds.py"

    orig_bounds = bounds_path.read_bytes()
    orig_test_bounds = test_bounds_path.read_bytes()

    try:
        evidence = await run_pytest_evidence(workspace, "test_bounds.py")
        assert evidence.exit_status == 0 and evidence.failed == 0, "Candidate tests failed"
        assert bounds_path.read_bytes() == orig_bounds, "Tests changed candidate source"
        assert test_bounds_path.read_bytes() == orig_test_bounds, "Tests changed themselves"

        for name, mutant in _CLAMP_MUTANTS.items():
            bounds_path.write_bytes(mutant.encode("utf-8"))
            evidence = await run_pytest_evidence(workspace, "test_bounds.py")
            assert evidence.exit_status == 1 and evidence.failed > 0, f"Mutant not rejected: {name}"

            assert bounds_path.read_bytes() == mutant.encode("utf-8"), f"Mutant changed: {name}"
            assert test_bounds_path.read_bytes() == orig_test_bounds, f"Tests changed: {name}"
    finally:
        bounds_path.write_bytes(orig_bounds)
        test_bounds_path.write_bytes(orig_test_bounds)


async def verify_clamp_documentation(workspace: Path) -> None:
    """Execute the required examples while preserving the implementation AST."""
    bounds_file = workspace / "bounds.py"
    original = bounds_file.read_bytes()
    baseline_source = repr(_CLAMP_SOURCE)

    script = "BASELINE = " + baseline_source + "\n" + """

import ast
import doctest
import sys
from pathlib import Path

# Add current directory to sys.path for importing bounds.py
sys.path.append(str(Path.cwd()))

def verify_docs():
    # Parse actual bounds.py UTF-8 and BASELINE.
    bounds_path = Path("bounds.py")
    with open(bounds_path, "r", encoding="utf-8") as f:
        actual_source = f.read()

    baseline_ast = ast.parse(BASELINE)
    actual_ast = ast.parse(actual_source)

    def strip_docstrings(tree):
        for node in ast.walk(tree):
            if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                if node.body and isinstance(node.body[0], ast.Expr) and isinstance(node.body[0].value, ast.Constant) and isinstance(node.body[0].value.value, str):
                    node.body.pop(0)
        return tree

    baseline_ast = strip_docstrings(baseline_ast)
    actual_ast = strip_docstrings(actual_ast)

    # assert ast.dump equality (implementation/signature preserved except docs).
    assert ast.dump(baseline_ast) == ast.dump(actual_ast), "Implementation or signature changed!"

    # Import bounds only after this check.
    import bounds

    # Parse bounds.clamp.__doc__ with DocTestParser.get_doctest using {"clamp":bounds.clamp}
    parser = doctest.DocTestParser()
    parsed_doc = parser.get_doctest(bounds.clamp.__doc__ or "", {"clamp": bounds.clamp}, "clamp", "bounds.py", 0)

    expected_examples = [
        ("clamp(-2,0,5)", "0"),
        ("clamp(3,0,5)", "3"),
        ("clamp(9,0,5)", "5"),
        ("clamp(0,4,1)", "ValueError: lower exceeds upper"),
    ]

    for i, (call_str, expected) in enumerate(expected_examples):
        found = False
        required_call_ast = ast.dump(ast.parse(call_str).body[0].value)

        for example in parsed_doc.examples:
            if example.options.get(doctest.SKIP):
                continue

            tree = ast.parse(example.source)
            if len(tree.body) != 1 or not isinstance(tree.body[0], ast.Expr):
                continue

            example_call_ast = ast.dump(tree.body[0].value)
            if example_call_ast == required_call_ast:
                if i < 3:
                    assert example.want.strip() == expected
                    assert example.exc_msg is None
                else:
                    assert example.exc_msg is not None, "Expected ValueError example"
                    assert example.exc_msg.strip() == expected
                found = True
                break
        assert found, f"Example {call_str} not found in doctests"

    # Actually run DocTestRunner().run(parsed_doc), assert failed==0 and attempted>=4.
    runner = doctest.DocTestRunner()
    result = runner.run(parsed_doc)
    assert result.failed == 0
    assert result.attempted >= 4
    assert bounds_path.read_text(encoding="utf-8") == actual_source, "Doctests changed source"

if __name__ == "__main__":
    verify_docs()
"""
    try:
        await verify_python(workspace, script)
        assert bounds_file.read_bytes() == original, "Doctests changed source"
    finally:
        bounds_file.write_bytes(original)


_CLAMP_TEST_STUB: str = """
import pytest
from bounds import clamp

def test_clamp():
    assert clamp(3, 0, 5) == 3
"""

async def run_test_docs_scenario(rig: EvalTestRig) -> EvalResult:
    """Deliver tests/docs and verify actual artifacts independently of final prose."""
    rig.create_file("bounds.py", _CLAMP_SOURCE)
    rig.create_file("test_bounds.py", _CLAMP_TEST_STUB)

    bounds_file = rig.test_dir / "bounds.py"
    test_bounds_file = rig.test_dir / "test_bounds.py"

    orig_bounds = bounds_file.read_bytes()
    orig_test_bounds = test_bounds_file.read_bytes()

    prompt = """Improve the documentation and tests for the clamp function in bounds.py.
The implementation and signature must stay unchanged except for the docstrings.
Tests should cover below/inside/above/equal/negative bounds and invalid range.
The function docstring must have direct doctest examples:
- clamp(-2,0,5)->0
- clamp(3,0,5)->3
- clamp(9,0,5)->5
- clamp(0,4,1) raising ValueError: lower exceeds upper, with actual traceback-style doctest.
"""

    result = await rig.run(prompt, max_iterations=12, timeout=300)

    assert result.success, result.error or result.final_response

    candidate_bounds = bounds_file.read_bytes()
    candidate_test_bounds = test_bounds_file.read_bytes()
    assert candidate_bounds != orig_bounds, "Documentation was not updated"
    assert candidate_test_bounds != orig_test_bounds, "Tests were not updated"

    await verify_clamp_documentation(rig.test_dir)
    await verify_clamp_tests(rig.test_dir)

    assert bounds_file.read_bytes() == candidate_bounds, "bounds.py changed after verification"
    assert test_bounds_file.read_bytes() == candidate_test_bounds, "test_bounds.py changed after verification"

    return result
