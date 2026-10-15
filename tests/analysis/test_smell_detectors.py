"""Behavioral contracts for reusable, conservative Python smell detectors."""

from __future__ import annotations

import ast
import copy
import textwrap
from collections.abc import Callable

import pytest
from scripts.smell_detector.detectors.deep_nesting import DeepNestingDetector
from scripts.smell_detector.detectors.duplicates import DuplicateCodeDetector
from scripts.smell_detector.detectors.long_method import LongMethodDetector

from henchman.analysis.smells.models import SmellInstance


def function_source(name: str = "calculate", expression: str = "value + 7") -> str:
    return (
        f"def {name}(value: int = 1) -> int:\n"
        '    """An example function."""\n'
        f"    result = {expression}\n"
        "    result = transform(result)\n"
        "    return result * 2\n"
    )


def duplicates(first: str, second: str) -> list[SmellInstance]:
    return DuplicateCodeDetector.detect_repo(
        {"first.py": ast.parse(first), "second.py": ast.parse(second)}
    )


@pytest.mark.parametrize(
    "change",
    [
        lambda source: source.replace("value + 7", "value + 8"),
        lambda source: source.replace("transform(result)", "other(result)"),
        lambda source: source.replace("value", "different"),
        lambda source: source.replace("int = 1", "int = 2"),
        lambda source: "@cached\n" + source,
        lambda source: source.replace("value + 7", "'production'"),
    ],
)
def test_distinct_syntax_does_not_claim_duplicate(
    change: Callable[[str], str],
) -> None:
    source = function_source()
    assert duplicates(source, change(source)) == []


def test_root_name_docstring_and_positions_do_not_hide_clone_candidate() -> None:
    first = function_source()
    second = "\n\n" + function_source("other").replace(
        "An example function.", "Different documentation."
    )
    findings = duplicates(first, second)
    assert len(findings) == 1
    finding = findings[0]
    assert finding.file == "second.py"
    assert finding.symbol_name == "other"
    assert "first.py:1" in finding.message
    assert "calculate" in finding.message
    assert "candidate" in finding.message.lower()
    assert "exact duplicate" not in finding.message.lower()


def test_incremental_duplicates_report_original_once_without_retaining_trees() -> None:
    from henchman.analysis.smells.duplicates import DuplicateIndex

    index = DuplicateIndex()
    for number in range(5):
        source = function_source(f"function_{number}")
        tree = ast.parse(source)
        before = copy.deepcopy(tree)
        findings = index.add(tree, source, f"file_{number}.py")
        assert ast.dump(tree, include_attributes=True) == ast.dump(before, include_attributes=True)
        assert len(findings) == (0 if number == 0 else 1)
        if findings:
            assert "file_0.py:1" in findings[0].message
    # A single representative is retained, rather than all source trees/pairs.
    assert len(index._representatives) == 1
    assert "FunctionDef" not in repr(vars(index))
    assert "result =" not in repr(vars(index))


def test_tiny_functions_are_not_duplicate_candidates() -> None:
    assert duplicates("def one(): return 1", "def two(): return 1") == []


def test_clone_candidates_have_qualified_class_and_nested_function_names() -> None:
    source = "class Container:\n" + textwrap.indent(function_source(), "    ")
    findings = duplicates(source, source.replace("Container", "Other"))
    assert findings[0].symbol_name == "Other.calculate"
    assert "Container.calculate" in findings[0].message


def test_long_method_counts_body_span_without_docstring_and_qualifies_symbols() -> None:
    body = "\n".join(f"        value_{number} = {number}" for number in range(30))
    source = 'class Service:\n    def run(self):\n        """Docs."""\n' + body
    (finding,) = LongMethodDetector().detect(ast.parse(source), source, "service.py")
    assert finding.symbol_name == "Service.run"
    assert "30 lines" in finding.message
    assert finding.line == 2
    assert finding.end_line == 33


def test_elif_alternatives_are_not_deep_nesting() -> None:
    source = "def choose(value):\n    if value == 0:\n        return 0\n"
    source += "".join(
        f"    elif value == {number}:\n        return {number}\n" for number in range(1, 7)
    )
    assert DeepNestingDetector().detect(ast.parse(source), source, "choose.py") == []


def test_deep_nesting_reports_only_worst_point_and_qualified_symbol() -> None:
    source = "class Service:\n    def run(self):\n"
    for depth in range(6):
        source += "    " * (depth + 2) + "if self.ready:\n"
    source += "    " * 8 + "return True\n"
    (finding,) = DeepNestingDetector().detect(ast.parse(source), source, "service.py")
    assert finding.symbol_name == "Service.run"
    assert "depth 6" in finding.message
    assert finding.line == 8


@pytest.mark.parametrize("control", ["match value:\n    case 1:", "try:"])
def test_match_and_exception_group_controls_contribute_to_depth(control: str) -> None:
    source = "def run(value):\n    if value:\n        for _ in range(2):\n"
    if control.startswith("match"):
        source += (
            "            match value:\n"
            "                case 1:\n"
            "                    if value:\n"
            "                        return value\n"
        )
    else:
        source += (
            "            try:\n"
            "                if value:\n"
            "                    return value\n"
            "            except* ValueError:\n"
            "                pass\n"
        )
    (finding,) = DeepNestingDetector().detect(ast.parse(source), source, "nested.py")
    assert "depth 4" in finding.message


def test_nested_function_depth_is_scoped_and_module_control_flow_ignored() -> None:
    source = "if True:\n    if True:\n        if True:\n            if True:\n"
    source += "                def outer():\n                    if True:\n"
    source += "                        def inner():\n"
    for depth in range(4):
        source += "    " * (depth + 7) + "if True:\n"
    source += "    " * 11 + "pass\n"
    (finding,) = DeepNestingDetector().detect(ast.parse(source), source, "nested.py")
    assert finding.symbol_name == "outer.inner"
    assert "depth 4" in finding.message


def test_real_nested_else_if_is_counted() -> None:
    source = "def choose(value):\n"
    for depth in range(4):
        source += "    " * (depth + 1) + "if value:\n"
        source += "    " * (depth + 2) + "pass\n"
        source += "    " * (depth + 1) + "else:\n"
    source += "    " * 5 + "pass\n"
    (finding,) = DeepNestingDetector().detect(ast.parse(source), source, "nested.py")
    assert "depth 4" in finding.message


def test_large_flat_elif_chain_does_not_exhaust_detector_recursion() -> None:
    source = "def choose(value):\n    if value == 0: return 0\n"
    source += "".join(f"    elif value == {number}: return {number}\n" for number in range(1, 1200))
    assert DeepNestingDetector().detect(ast.parse(source), source, "wide.py") == []
