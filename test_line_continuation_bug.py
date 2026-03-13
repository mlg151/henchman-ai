#!/usr/bin/env python3
"""Test for line continuation bug - to be added to test_intelligent_context.py"""

def test_extract_code_blocks_line_continuation_whitespace_bug():
    """Test that line continuation preserves whitespace on continued line.
    
    This test exposes a bug where whitespace after a backslash-newline
    line continuation is lost during code block extraction.
    
    BUG: String `'hello \\\n world'` is extracted as `'hello \\\nworld'`
    (missing space after newline).
    """
    # Test 1: Line continuation with space after newline
    content1 = '''```python
s = 'hello \\
 world'  # Space after newline should be preserved
print(repr(s))
```'''
    
    # The string should be extracted exactly as-is
    # 'hello \\\n world' (backslash, newline, space, world)
    # When executed: 'hello  world' (two spaces)
    
    from henchman.utils.intelligent_context import ContentExtractor
    blocks1 = ContentExtractor.extract_code_blocks(content1)
    assert len(blocks1) == 1, f"Expected 1 code block, got {len(blocks1)}"
    
    block1 = blocks1[0]
    print(f"Extracted block:\n{block1}")
    
    # Check that space after newline is preserved
    # The block should contain: 'hello \\\n world'
    lines = block1.split('\n')
    # Find the line with the string
    for line in lines:
        if "s = " in line:
            print(f"String line: {repr(line)}")
            # Should have space after newline in source
            if ' \\\n world' not in block1 and ' \\\nworld' in block1:
                print("BUG CONFIRMED: Space after newline is missing!")
                print(f"Expected: 'hello \\\\n world'")
                print(f"Got: {repr(line)}")
                # This assertion will fail, demonstrating the bug
                assert ' \\\n world' in block1, f"Space after newline not preserved: {block1}"
            break
    
    # Test 2: Line continuation with indentation
    content2 = '''```python
def foo():
    s = 'hello \\
         world'  # Indented continuation
    return s
```'''
    
    blocks2 = ContentExtractor.extract_code_blocks(content2)
    assert len(blocks2) == 1, f"Expected 1 code block, got {len(blocks2)}"
    
    block2 = blocks2[0]
    print(f"\nTest 2 extracted block:\n{block2}")
    
    # Should preserve indentation after newline
    assert '         world' in block2, f"Indentation after line continuation not preserved: {block2}"

if __name__ == "__main__":
    test_extract_code_blocks_line_continuation_whitespace_bug()
    print("\nTest completed.")