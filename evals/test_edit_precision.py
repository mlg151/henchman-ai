"""Edit precision evals (Cline Diff-Edit style).

These tests verify that the agent can make targeted edits without
breaking surrounding code or making unintended changes.
"""

import ast
import subprocess

from evals.helpers import EvalResult, EvalTestRig, eval_test, verify_python


@eval_test("ALWAYS_PASSES")
async def test_edit_single_line_preserves_rest(rig: EvalTestRig) -> None:
    """Agent should edit one line without changing others."""
    original_code = '''"""Module docstring."""

def function_one():
    """First function."""
    return 1

def function_two():
    """Second function."""
    return 2  # This should become 42

def function_three():
    """Third function."""
    return 3
'''
    rig.create_file("module.py", original_code)

    await rig.run(
        "In module.py, change function_two to return 42 instead of 2. "
        "Do not modify any other functions."
    )

    # Verify the edit
    content = rig.read_file("module.py")

    # function_two should return 42
    assert "return 42" in content, "function_two should return 42"

    # Other functions should be unchanged
    assert "def function_one():" in content
    assert "def function_three():" in content
    assert content.count("return 1") == 1, "function_one should still return 1"
    assert content.count("return 3") == 1, "function_three should still return 3"

    # The file should still be valid Python
    result = subprocess.run(
        ["python", "-m", "py_compile", "module.py"],
        cwd=rig.test_dir,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"Code should be valid Python: {result.stderr}"


async def run_add_method_to_class_scenario(rig: EvalTestRig) -> EvalResult:
    """Agent should add a method without breaking the class."""
    rig.create_file(
        "calculator.py",
        '''"""Simple calculator class."""

class Calculator:
    """A basic calculator."""

    def __init__(self):
        self.result = 0

    def add(self, x):
        """Add x to result."""
        self.result += x
        return self.result

    def subtract(self, x):
        """Subtract x from result."""
        self.result -= x
        return self.result

    def clear(self):
        """Reset the result."""
        self.result = 0
        return self.result
''',
    )

    original = ast.parse(rig.read_file("calculator.py"))
    result = await rig.run(
        "Add a 'multiply' method to the Calculator class in calculator.py. "
        "It should multiply self.result by x and return the new result. "
        "Do not modify existing methods."
    )

    assert result.success, result.error or result.final_response
    updated = ast.parse(rig.read_file("calculator.py"))
    original_class = next(node for node in original.body if isinstance(node, ast.ClassDef))
    classes = [
        node for node in updated.body
        if isinstance(node, ast.ClassDef) and node.name == "Calculator"
    ]
    assert len(classes) == 1, "Expected one Calculator class"
    for method in original_class.body:
        if isinstance(method, ast.FunctionDef):
            matches = [
                node for node in classes[0].body
                if isinstance(node, ast.FunctionDef) and node.name == method.name
            ]
            assert len(matches) == 1, f"Original method {method.name} was removed or duplicated"
            assert ast.dump(matches[0]) == ast.dump(method), (
                f"Original method {method.name} was modified"
            )
    checks = """
from calculator import Calculator
c = Calculator()
assert c.add(5) == 5
assert c.subtract(2) == 3
assert c.clear() == 0
assert c.result == 0
c.add(4)
assert c.multiply(3) == 12
assert c.result == 12
assert c.multiply(-2) == -24
assert c.result == -24
assert c.multiply(0) == 0
assert c.result == 0
assert c.add(-3) == -3
assert c.multiply(-2) == 6
assert c.multiply(2) == 12
assert c.result == 12
"""
    rig.create_file("test_calc.py", checks)
    await verify_python(rig.test_dir, checks)
    return result


@eval_test("ALWAYS_PASSES")
async def test_add_method_to_class(rig: EvalTestRig) -> None:
    """Preserve existing methods while adding stateful multiplication."""
    await run_add_method_to_class_scenario(rig)


@eval_test("USUALLY_PASSES")
async def test_fix_bug_preserve_formatting(rig: EvalTestRig) -> None:
    """Agent should fix a bug while preserving code formatting."""
    rig.create_file(
        "utils.py",
        '''"""Utility functions with specific formatting."""

# Configuration constants
MAX_RETRIES = 3
TIMEOUT_SECONDS = 30

def safe_divide(a, b):
    """
    Safely divide a by b.

    Args:
        a: The numerator
        b: The denominator

    Returns:
        The result of a/b, or None if b is zero
    """
    if b == 0:
        return 0  # BUG: should return None, not 0
    return a / b


def clamp(value, min_val, max_val):
    """Clamp value between min and max."""
    return max(min_val, min(value, max_val))
''',
    )

    await rig.run(
        "Fix the bug in safe_divide in utils.py - it should return None when b is zero, not 0. "
        "Preserve the existing formatting and comments."
    )

    content = rig.read_file("utils.py")

    # Bug should be fixed
    assert "return None" in content, "Should return None for division by zero"

    # Formatting should be preserved
    assert "MAX_RETRIES = 3" in content, "Constants should be preserved"
    assert "TIMEOUT_SECONDS = 30" in content
    assert '"""Utility functions' in content, "Module docstring should be preserved"
    assert "def clamp(" in content, "Other functions should be preserved"

    # Verify it works correctly
    result = subprocess.run(
        ["python", "-c", "from utils import safe_divide; assert safe_divide(1, 0) is None"],
        cwd=rig.test_dir,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"Fixed function should work: {result.stderr}"


async def run_rename_variable_consistently_scenario(rig: EvalTestRig) -> EvalResult:
    """Agent should rename a variable consistently throughout a file."""
    rig.create_file(
        "processor.py",
        '''"""Data processor module."""

def process_data(data):
    """Process the input data."""
    tmp = []
    for item in data:
        tmp.append(item * 2)
    return tmp


def filter_data(data):
    """Filter the input data."""
    tmp = []
    for item in data:
        if item > 0:
            tmp.append(item)
    return tmp


def transform_data(data):
    """Transform the input data."""
    tmp = data.copy()
    tmp.reverse()
    return tmp
''',
    )

    original = ast.parse(rig.read_file("processor.py"))
    result = await rig.run(
        "In processor.py, rename all variables called 'tmp' to 'result' for better clarity. "
        "Make sure to rename consistently in all functions."
    )

    assert result.success, result.error or result.final_response
    # The requested change is only a local rename; preserve the surrounding AST.
    for node in ast.walk(original):
        if isinstance(node, ast.Name) and node.id == "tmp":
            node.id = "result"
    updated = ast.parse(rig.read_file("processor.py"))
    assert ast.dump(updated) == ast.dump(original), (
        "Expected tmp bindings and references renamed to result with other code preserved"
    )
    checks = """
from processor import process_data, filter_data, transform_data
assert process_data([1, 2, 3]) == [2, 4, 6]
assert filter_data([-1, 0, 1, 2]) == [1, 2]
assert transform_data([1, 2, 3]) == [3, 2, 1]
for values in ([], [-2, 0, 3, 3], [1]):
    for function, expected in (
        (process_data, [item * 2 for item in values]),
        (filter_data, [item for item in values if item > 0]),
        (transform_data, list(reversed(values))),
    ):
        original = list(values)
        assert function(values) == expected
        assert values == original, f"{function.__name__} mutated its input"
"""
    rig.create_file("test_processor.py", checks)
    await verify_python(rig.test_dir, checks)
    return result


@eval_test("USUALLY_PASSES")
async def test_rename_variable_consistently(rig: EvalTestRig) -> None:
    """Rename scoped variables while preserving code and input values."""
    await run_rename_variable_consistently_scenario(rig)


@eval_test("USUALLY_PASSES")
async def test_add_error_handling(rig: EvalTestRig) -> None:
    """Agent should add error handling without breaking existing logic."""
    rig.create_file(
        "file_ops.py",
        '''"""File operations module."""

def read_json(filepath):
    """Read and parse a JSON file."""
    import json
    with open(filepath) as f:
        return json.load(f)


def write_json(filepath, data):
    """Write data to a JSON file."""
    import json
    with open(filepath, 'w') as f:
        json.dump(data, f)
''',
    )

    await rig.run(
        "Add error handling to both functions in file_ops.py. "
        "They should catch FileNotFoundError and json.JSONDecodeError and return None "
        "instead of raising exceptions. Preserve the existing functionality for valid inputs."
    )

    # Test error handling
    result = subprocess.run(
        [
            "python",
            "-c",
            """
from file_ops import read_json
result = read_json('nonexistent.json')
assert result is None, f"Should return None for missing file, got {result}"
print("Error handling works!")
""",
        ],
        cwd=rig.test_dir,
        capture_output=True,
        text=True,
        timeout=5,
    )
    assert result.returncode == 0, f"Error handling should work: {result.stderr}\n{result.stdout}"

    # Test normal operation still works
    rig.create_file("test.json", '{"key": "value"}')
    result = subprocess.run(
        [
            "python",
            "-c",
            """
from file_ops import read_json
result = read_json('test.json')
assert result == {"key": "value"}, f"Normal operation should work, got {result}"
print("Normal operation works!")
""",
        ],
        cwd=rig.test_dir,
        capture_output=True,
        text=True,
        timeout=5,
    )
    assert result.returncode == 0, f"Normal operation should work: {result.stderr}\n{result.stdout}"


async def run_multi_file_edit_scenario(rig: EvalTestRig) -> EvalResult:
    """Agent should edit multiple files correctly."""
    rig.create_file(
        "models.py",
        '''"""Data models."""

class User:
    def __init__(self, name):
        self.name = name

    def greet(self):
        return f"Hello, {self.name}"
''',
    )

    rig.create_file(
        "app.py",
        '''"""Main application."""
from models import User

def main():
    user = User("World")
    print(user.greet())

if __name__ == "__main__":
    main()
''',
    )

    result = await rig.run(
        "Add an 'email' parameter to the User class in models.py (with a default of None), "
        "and update app.py to pass an email when creating the User."
    )

    assert result.success, result.error or result.final_response
    await verify_python(rig.test_dir, """
from inspect import signature
from unittest.mock import patch
import models

user_type = models.User
legacy = user_type("Legacy")
assert legacy.name == "Legacy"
assert legacy.email is None
assert legacy.greet() == "Hello, Legacy"
explicit = user_type("Ada", email="ada@example.test")
assert explicit.name == "Ada"
assert explicit.email == "ada@example.test"
assert explicit.greet() == "Hello, Ada"
assert user_type("Empty", email=None).email is None
calls = []
constructor = signature(user_type)
def observe(*args, **kwargs):
    supplied = constructor.bind(*args, **kwargs).arguments.get("email")
    user = user_type(*args, **kwargs)
    calls.append((supplied, user.name, user.email))
    return user
with patch.object(models, "User", side_effect=observe):
    import app
    calls.clear()
    app.main()
assert calls, "app.main did not construct User"
assert any(
    isinstance(supplied, str) and supplied.strip()
    and name == "World" and stored_email == supplied
    for supplied, name, stored_email in calls
), "app.main did not pass a nonempty email to User"
""")
    return result


@eval_test("USUALLY_PASSES")
async def test_multi_file_edit(rig: EvalTestRig) -> None:
    """Preserve User compatibility and verify the actual updated caller."""
    await run_multi_file_edit_scenario(rig)
