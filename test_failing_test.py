#!/usr/bin/env python3
"""Write a failing test to demonstrate a bug."""

import sys
sys.path.insert(0, '/home/matthew/mlg-cli/src')

from henchman.utils.intelligent_context import ContentExtractor
import pytest

def test_extract_code_blocks_backslash_newline():
    """Test extracting code blocks with backslash-newline line continuation.
    
    This test exposes a bug where backslash-newline is not handled correctly.
    """
    # Backslash at end of line continues the string
    content = '''```python
x = 'hello \\
world'
```'''
    result = ContentExtractor.extract_code_blocks(content)
    assert len(result) == 1, f"Expected 1 code block, got {len(result)}"
    
    # The code block should preserve the backslash-newline
    block = result[0]
    assert 'hello \\\n world' in block, f"Backslash-newline not preserved: {repr(block)}"

def test_extract_code_blocks_raw_string_odd_backslash():
    """Test raw strings with odd number of backslashes before quote.
    
    This test might expose a bug in backslash counting.
    """
    # r'\"' - odd number of backslashes (1) escapes quote
    content = '''```python
print(r'\\"')
```'''
    result = ContentExtractor.extract_code_blocks(content)
    assert len(result) == 1, f"Expected 1 code block, got {len(result)}"
    
    # r'\\"' - even number of backslashes (2) doesn't escape quote
    # This should be a syntax error in actual Python
    content2 = '''```python
print(r'\\\\"')
```'''
    result2 = ContentExtractor.extract_code_blocks(content2)
    assert len(result2) == 1, f"Expected 1 code block, got {len(result2)}"

if __name__ == "__main__":
    # Run the tests
    test_extract_code_blocks_backslash_newline()
    test_extract_code_blocks_raw_string_odd_backslash()
    print("All tests passed!")