"""Coding task evals (Cline/Exercism-style).

These tests verify that the agent can complete programming tasks correctly.
Unlike behavioral evals that check tool usage, these verify the actual output.
"""

import subprocess

from evals.helpers import eval_test


@eval_test("ALWAYS_PASSES")
async def test_write_hello_world(rig) -> None:
    """Agent should write a working hello world program."""
    await rig.run("Create a Python file called hello.py that prints 'Hello, World!'")

    # Verify file exists
    assert rig.file_exists("hello.py"), "hello.py should be created"

    # Verify it runs correctly
    result = subprocess.run(
        ["python", "hello.py"],
        cwd=rig.test_dir,
        capture_output=True,
        text=True,
        timeout=5,
    )
    assert result.returncode == 0, f"Script should run without error: {result.stderr}"
    assert "Hello, World!" in result.stdout, f"Output should contain greeting: {result.stdout}"


@eval_test("ALWAYS_PASSES")
async def test_write_function_with_tests(rig) -> None:
    """Agent should write a function that passes given test cases."""
    await rig.run(
        "Create a Python file called math_utils.py with a function called 'add' "
        "that takes two numbers and returns their sum."
    )

    assert rig.file_exists("math_utils.py"), "math_utils.py should be created"

    # Write a test file and run it
    rig.create_file(
        "test_math.py",
        """
from math_utils import add

def test_add():
    assert add(2, 3) == 5
    assert add(-1, 1) == 0
    assert add(0, 0) == 0
    assert add(100, 200) == 300

if __name__ == "__main__":
    test_add()
    print("All tests passed!")
""",
    )

    result = subprocess.run(
        ["python", "test_math.py"],
        cwd=rig.test_dir,
        capture_output=True,
        text=True,
        timeout=5,
    )
    assert result.returncode == 0, f"Tests should pass: {result.stderr}"
    assert "All tests passed!" in result.stdout


@eval_test("ALWAYS_PASSES")
async def test_fix_syntax_error(rig) -> None:
    """Agent should fix a syntax error in code."""
    # Create a file with a syntax error
    rig.create_file(
        "broken.py",
        """
def greet(name):
    print(f"Hello, {name}!"
    return True
""",
    )

    await rig.run("Fix the syntax error in broken.py")

    # Verify the file now runs
    result = subprocess.run(
        ["python", "-c", "import broken; broken.greet('World')"],
        cwd=rig.test_dir,
        capture_output=True,
        text=True,
        timeout=5,
    )
    assert result.returncode == 0, f"Fixed code should run: {result.stderr}"


@eval_test("USUALLY_PASSES")
async def test_implement_fizzbuzz(rig) -> None:
    """Agent should implement FizzBuzz correctly."""
    await rig.run(
        "Create fizzbuzz.py with a function called 'fizzbuzz' that takes a number n "
        "and returns a list of strings from 1 to n where: "
        "- numbers divisible by 3 are replaced with 'Fizz', "
        "- numbers divisible by 5 are replaced with 'Buzz', "
        "- numbers divisible by both are replaced with 'FizzBuzz', "
        "- other numbers are converted to strings."
    )

    assert rig.file_exists("fizzbuzz.py"), "fizzbuzz.py should be created"

    # Test it
    rig.create_file(
        "test_fizzbuzz.py",
        """
from fizzbuzz import fizzbuzz

def test_fizzbuzz():
    result = fizzbuzz(15)
    assert result[0] == "1"
    assert result[2] == "Fizz"      # 3
    assert result[4] == "Buzz"      # 5
    assert result[5] == "Fizz"      # 6
    assert result[9] == "Buzz"      # 10
    assert result[14] == "FizzBuzz" # 15
    assert len(result) == 15

if __name__ == "__main__":
    test_fizzbuzz()
    print("FizzBuzz tests passed!")
""",
    )

    result = subprocess.run(
        ["python", "test_fizzbuzz.py"],
        cwd=rig.test_dir,
        capture_output=True,
        text=True,
        timeout=5,
    )
    assert result.returncode == 0, f"FizzBuzz tests should pass: {result.stderr}\n{result.stdout}"


@eval_test("USUALLY_PASSES")
async def test_implement_fibonacci(rig) -> None:
    """Agent should implement Fibonacci sequence correctly."""
    await rig.run(
        "Create fibonacci.py with a function called 'fib' that takes n and "
        "returns the nth Fibonacci number (0-indexed, so fib(0)=0, fib(1)=1, fib(2)=1, etc.)"
    )

    assert rig.file_exists("fibonacci.py"), "fibonacci.py should be created"

    rig.create_file(
        "test_fib.py",
        """
from fibonacci import fib

def test_fib():
    assert fib(0) == 0
    assert fib(1) == 1
    assert fib(2) == 1
    assert fib(3) == 2
    assert fib(4) == 3
    assert fib(5) == 5
    assert fib(10) == 55

if __name__ == "__main__":
    test_fib()
    print("Fibonacci tests passed!")
""",
    )

    result = subprocess.run(
        ["python", "test_fib.py"],
        cwd=rig.test_dir,
        capture_output=True,
        text=True,
        timeout=5,
    )
    assert result.returncode == 0, f"Fibonacci tests should pass: {result.stderr}\n{result.stdout}"


@eval_test("USUALLY_PASSES")
async def test_refactor_to_class(rig) -> None:
    """Agent should refactor functions into a class."""
    rig.create_file(
        "counter.py",
        """
count = 0

def increment():
    global count
    count += 1
    return count

def decrement():
    global count
    count -= 1
    return count

def get_count():
    return count

def reset():
    global count
    count = 0
""",
    )

    await rig.run(
        "Refactor counter.py to use a Counter class instead of global variables. "
        "The class should have increment(), decrement(), get_count(), and reset() methods."
    )

    # Test the refactored class
    rig.create_file(
        "test_counter.py",
        """
from counter import Counter

def test_counter():
    c = Counter()
    assert c.get_count() == 0
    assert c.increment() == 1
    assert c.increment() == 2
    assert c.decrement() == 1
    c.reset()
    assert c.get_count() == 0

if __name__ == "__main__":
    test_counter()
    print("Counter tests passed!")
""",
    )

    result = subprocess.run(
        ["python", "test_counter.py"],
        cwd=rig.test_dir,
        capture_output=True,
        text=True,
        timeout=5,
    )
    assert result.returncode == 0, f"Counter tests should pass: {result.stderr}\n{result.stdout}"
