#!/usr/bin/env python3
"""Comprehensive test to exercise _process_char paths."""

from henchman.utils.intelligent_context import ContentExtractor

# Test cases designed to exercise different code paths in _process_char
test_cases = [
    # Basic code block
    ("Simple code block", '''```python\nprint("hello")\n```''', 1),
    
    # Code block with string containing quote
    ("String with quote", '''```python\ns = "he said \\"hello\\""\n```''', 1),
    
    # Code block with apostrophe in word
    ("Apostrophe in word", '''```python\nprint("isn't")\n```''', 1),
    
    # Code block with raw string
    ("Raw string", '''```python\ns = r"hello\\n"\n```''', 1),
    
    # Code block with raw bytes string
    ("Raw bytes string", '''```python\ns = br"hello\\n"\n```''', 1),
    
    # Code block with formatted raw string
    ("Formatted raw string", '''```python\ns = fr"hello {name}\\n"\n```''', 1),
    
    # Code block with triple-quoted string
    ("Triple-quoted string", '''```python\ns = """hello\nworld"""\n```''', 1),
    
    # Code block with comment
    ("With comment", '''```python\n# This is a comment\nprint("hello")\n```''', 1),
    
    # Code block with backticks in string
    ("Backticks in string", '''```python\ns = "`code`"\n```''', 1),
    
    # Code block with escaped backtick in string
    ("Escaped backtick", '''```python\ns = "\\`"\n```''', 1),
    
    # Nested code block in string (should not be extracted)
    ("Nested code in string", '''```python\ns = "```python\\nprint(1)\\n```"\n```''', 1),
    
    # Multiple code blocks
    ("Multiple blocks", '''```python\nprint(1)\n```\nText\n```python\nprint(2)\n```''', 2),
    
    # Code block with line continuation (acknowledged bug)
    ("Line continuation", '''```python\ns = "hello\\\\\\nworld"\n```''', 1),
    
    # Code block with invalid string prefix (should still extract)
    ("Invalid prefix", '''```python\ns = rr"hello"  # invalid\n```''', 1),
    
    # Code block with unicode prefix (u)
    ("Unicode prefix", '''```python\ns = u"hello"\n```''', 1),
    
    # Code block with mixed case prefix
    ("Mixed case prefix", '''```python\ns = R"hello"\n```''', 1),
]

print("Running comprehensive tests...")
all_pass = True

for name, content, expected in test_cases:
    try:
        result = ContentExtractor.extract_code_blocks(content)
        if len(result) != expected:
            print(f"✗ {name}: expected {expected} blocks, got {len(result)}")
            print(f"  Content: {repr(content[:100])}...")
            all_pass = False
        else:
            print(f"✓ {name}")
    except Exception as e:
        print(f"✗ {name}: {type(e).__name__}: {e}")
        print(f"  Content: {repr(content[:100])}...")
        all_pass = False

if all_pass:
    print("\nAll tests passed!")
else:
    print("\nSome tests failed - potential bug found!")