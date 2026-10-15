"""Final test for unreachable yield bug - will FAIL with current code."""

import pytest


def test_unreachable_yield_exists():
    """Test that finds the exact unreachable yield bug."""
    with open('src/henchman/cli/textual_mixins.py') as f:
        lines = f.readlines()

    # Find the method
    in_method = False
    method_start = None

    for i, line in enumerate(lines):
        if 'async def chat_completion_stream' in line and 'self: _NullProvider' in lines[i+1] if i+1 < len(lines) else False:
            in_method = True
            method_start = i
            continue

        if in_method and line.strip() and not line.startswith(' ') and not line.startswith('\n'):
            # End of method
            break

    if method_start is None:
        pytest.skip("Could not find chat_completion_stream method")

    # Check method body for raise then yield
    found_raise = False
    raise_line = None

    for i in range(method_start, min(method_start + 20, len(lines))):
        line = lines[i]

        if '"""Raise an error indicating no provider is configured."""' in line:
            # Skip docstring
            continue

        if 'raise RuntimeError(_NO_PROVIDER_MSG)' in line:
            found_raise = True
            raise_line = i
            # Check next non-empty, non-comment line
            for j in range(i + 1, min(i + 5, len(lines))):
                next_line = lines[j].strip()
                if next_line and not next_line.startswith('#'):
                    if 'yield' in next_line:
                        print("BUG CONFIRMED: Unreachable yield after raise!")
                        print(f"  Line {raise_line + 1}: {lines[raise_line].rstrip()}")
                        print(f"  Line {j + 1}: {lines[j].rstrip()}")
                        print(f"  The yield on line {j + 1} is unreachable because raise on line {raise_line + 1} always executes first.")
                        pytest.fail(f"Unreachable yield statement at line {j + 1}")
                    break
            break

    if not found_raise:
        print("Warning: Could not find raise statement in method")

    print("Test passed: No unreachable yield found (or bug already fixed)")
    # If we get here, either no bug or already fixed
