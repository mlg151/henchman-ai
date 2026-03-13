#!/usr/bin/env python3
"""Failing test for newline escaped bug."""

import pytest
from henchman.utils.intelligent_context import ContentExtractor

def test_string_with_line_continuation():
    """Test that strings with line continuation are handled correctly.
    
    The bug: parser ends string at newline even when newline is escaped
    (preceded by backslash for line continuation).
    """
    # Create a test that should fail with current implementation
    # String with line continuation followed by backticks
    content = '''Some text
```python
s = "hello\\
```world"
print(s)
```
More text'''
    
    # With bug: parser ends string at newline (line 3), sees ``` on line 4,
    # thinks it's ending code block, extracts lines 2-4 only
    # Without bug: parser recognizes string continues, extracts lines 2-6
    
    blocks = ContentExtractor.extract_code_blocks(content)
    
    # Should extract 1 code block (lines 2-6)
    assert len(blocks) == 1, f"Expected 1 code block, got {len(blocks)}. Parser incorrectly ended string at newline due to line continuation bug."
    
    block = blocks[0]
    # Should contain the full string with backticks
    assert '```world"' in block, f"Backticks after line continuation not preserved: {block}"
    
    # Also test simple case
    content2 = '''```python
s = "hello\\
world"
print(s)
```'''
    
    blocks2 = ContentExtractor.extract_code_blocks(content2)
    assert len(blocks2) == 1, f"Simple line continuation failed: expected 1 block, got {len(blocks2)}"
    
    # The bug is in _process_char: when char == "\n" and in_string and not triple_quote,
    # it ends string without checking if was_escaped

if __name__ == "__main__":
    try:
        test_string_with_line_continuation()
        print("Test PASSED - bug may already be fixed or test doesn't trigger it")
    except AssertionError as e:
        print(f"Test FAILED: {e}")
        print("Bug confirmed!")