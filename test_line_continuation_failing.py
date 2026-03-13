#!/usr/bin/env python3
"""Failing test for line continuation bug."""

import pytest
from henchman.utils.intelligent_context import ContentExtractor

def test_line_continuation_in_string():
    """Test that line continuation in strings is handled correctly.
    
    This test should FAIL because the parser doesn't track line continuation
    (backslash at end of line in non-triple-quoted string).
    """
    # String with line continuation
    content = '''```python
s = "hello\\
world"
print(s)
```'''
    
    # Extract code block
    blocks = ContentExtractor.extract_code_blocks(content)
    
    # Should extract exactly one code block
    assert len(blocks) == 1, f"Expected 1 code block, got {len(blocks)}"
    
    block = blocks[0]
    # The code block should contain the string with line continuation
    # The parser should recognize that the string continues across the newline
    # If it incorrectly ends the string at newline, backticks on next line
    # might be misinterpreted
    
    # Actually, the extracted code block would still be correct
    # because the source code is preserved
    # The bug is in the parser's internal state tracking, not in extraction
    
    # Let me test a more specific case: string with line continuation containing backticks
    content2 = '''Some text
```python
s = "hello\\
```world"
print(s)
```
More text'''
    
    blocks2 = ContentExtractor.extract_code_blocks(content2)
    # Should extract 1 code block (lines 2-6)
    # If parser incorrectly ends string at newline, it might see ``` on line 4
    # as ending the code block, extracting lines 2-4 only
    assert len(blocks2) == 1, f"Expected 1 code block, got {len(blocks2)}. Parser may have incorrectly ended code block early due to line continuation bug."
    
    block2 = blocks2[0]
    # Should contain the full string
    assert '```world"' in block2, f"Backticks after line continuation not preserved: {block2}"

if __name__ == "__main__":
    # Run the test
    try:
        test_line_continuation_in_string()
        print("Test PASSED (bug may be fixed)")
    except AssertionError as e:
        print(f"Test FAILED: {e}")
        print("Bug confirmed!")