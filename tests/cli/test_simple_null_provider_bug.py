"""Simple test for unreachable yield bug."""

import re
import pytest


def test_unreachable_yield_in_null_provider():
    """Simple regex test for unreachable yield."""
    with open('src/henchman/cli/textual_mixins.py', 'r') as f:
        content = f.read()
    
    # Find _NullProvider class
    # Look for pattern: raise ... yield
    # Using regex to find raise then yield on next line
    
    # First find the method
    method_pattern = r'async def chat_completion_stream\([^)]*\)[^:]*:[^{]*{(.*?)^\s*(?=async def|\s*def|\s*class|\Z)'
    method_match = re.search(method_pattern, content, re.DOTALL | re.MULTILINE)
    
    if not method_match:
        pytest.skip("Could not find chat_completion_stream method")
    
    method_body = method_match.group(1)
    
    # Check for raise then yield pattern
    lines = method_body.split('\n')
    in_null_provider = '_NullProvider' in content[:method_match.start()]
    
    if not in_null_provider:
        pytest.skip("Method not in _NullProvider class")
    
    # Look for raise statement
    for i, line in enumerate(lines):
        if 'raise RuntimeError(_NO_PROVIDER_MSG)' in line:
            # Check next non-empty, non-comment line
            for j in range(i + 1, len(lines)):
                next_line = lines[j].strip()
                if next_line and not next_line.startswith('#'):
                    if 'yield' in next_line:
                        print(f"BUG FOUND: raise on line ~{i}, yield on line ~{j}")
                        print(f"  Raise line: {line.strip()}")
                        print(f"  Yield line: {next_line}")
                        pytest.fail("Unreachable yield after raise statement")
                    break
            break
    
    print("No unreachable yield found (or already fixed)")
    # Test passes if no bug found