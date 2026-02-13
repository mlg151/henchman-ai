"""Edit precision evals (Cline Diff-Edit style).

These tests verify that the agent can make targeted edits without
breaking surrounding code or making unintended changes.
"""

import subprocess

from evals.helpers import eval_test


@eval_test("ALWAYS_PASSES")
async def test_edit_single_line_preserves_rest(rig) -> None:
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


@eval_test("ALWAYS_PASSES")
async def test_add_method_to_class(rig) -> None:
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

    await rig.run(
        "Add a 'multiply' method to the Calculator class in calculator.py. "
        "It should multiply self.result by x and return the new result. "
        "Do not modify existing methods."
    )

    # Verify the class still works
    rig.create_file(
        "test_calc.py",
        """
from calculator import Calculator

def test_calculator():
    c = Calculator()
    # Test existing methods still work
    assert c.add(5) == 5
    assert c.subtract(2) == 3
    c.clear()
    assert c.result == 0

    # Test new multiply method
    c.add(4)
    assert c.multiply(3) == 12

if __name__ == "__main__":
    test_calculator()
    print("Calculator tests passed!")
""",
    )

    result = subprocess.run(
        ["python", "test_calc.py"],
        cwd=rig.test_dir,
        capture_output=True,
        text=True,
        timeout=5,
    )
    assert result.returncode == 0, f"Calculator tests should pass: {result.stderr}\n{result.stdout}"


@eval_test("USUALLY_PASSES")
async def test_fix_bug_preserve_formatting(rig) -> None:
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


@eval_test("USUALLY_PASSES")
async def test_rename_variable_consistently(rig) -> None:
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

    await rig.run(
        "In processor.py, rename all variables called 'tmp' to 'result' for better clarity. "
        "Make sure to rename consistently in all functions."
    )

    content = rig.read_file("processor.py")

    # 'tmp' should be replaced with 'result' everywhere
    assert "tmp" not in content, "All 'tmp' should be renamed to 'result'"
    assert content.count("result") >= 6, "Should have 'result' in all three functions"

    # Code should still work
    rig.create_file(
        "test_processor.py",
        """
from processor import process_data, filter_data, transform_data

def test_all():
    assert process_data([1, 2, 3]) == [2, 4, 6]
    assert filter_data([-1, 0, 1, 2]) == [1, 2]
    assert transform_data([1, 2, 3]) == [3, 2, 1]

if __name__ == "__main__":
    test_all()
    print("Processor tests passed!")
""",
    )

    result = subprocess.run(
        ["python", "test_processor.py"],
        cwd=rig.test_dir,
        capture_output=True,
        text=True,
        timeout=5,
    )
    assert result.returncode == 0, f"Processor tests should pass: {result.stderr}\n{result.stdout}"


@eval_test("USUALLY_PASSES")
async def test_add_error_handling(rig) -> None:
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


@eval_test("USUALLY_PASSES")
async def test_multi_file_edit(rig) -> None:
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

    await rig.run(
        "Add an 'email' parameter to the User class in models.py (with a default of None), "
        "and update app.py to pass an email when creating the User."
    )

    # Verify both files were updated correctly
    models_content = rig.read_file("models.py")
    assert "email" in models_content, "User class should have email parameter"

    app_content = rig.read_file("app.py")
    assert "email" in app_content.lower() or "@" in app_content, "app.py should pass an email"

    # Verify the code runs
    result = subprocess.run(
        ["python", "app.py"],
        cwd=rig.test_dir,
        capture_output=True,
        text=True,
        timeout=5,
    )
    assert result.returncode == 0, f"App should run: {result.stderr}"
