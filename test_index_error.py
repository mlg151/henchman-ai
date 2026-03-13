#!/usr/bin/env python3
"""Test for potential IndexError."""

from henchman.utils.intelligent_context import ContentExtractor

# Test edge cases that might cause IndexError
test_cases = [
    ("Empty string", ""),
    ("Single backtick", "`"),
    ("Two backticks", "``"),
    ("Single quote", "'"),
    ("Double quote", '"'),
    ("Backslash", "\\"),
    ("Newline", "\n"),
    ("Hash", "#"),
    ("String at end", '"hello'),
    ("Escaped quote at end", '\\"'),
    ("Raw string prefix at end", 'r'),
    ("Multiple prefixes at end", 'br'),
]

print("Testing edge cases for IndexError...")
for name, content in test_cases:
    try:
        result = ContentExtractor.extract_code_blocks(content)
        print(f"✓ {name}: No error")
    except Exception as e:
        print(f"✗ {name}: {type(e).__name__}: {e}")

# Test with code blocks
print("\nTesting code block extraction edge cases...")
test_cases2 = [
    ("Incomplete code block", "```python\nprint('hello')"),
    ("Just opening fence", "```"),
    ("Opening fence with newline", "```\n"),
    ("Nested backticks in string", '```python\ns = "`"\n```'),
    ("Backtick at end of string", '```python\ns = "`"\n```'),
]

for name, content in test_cases2:
    try:
        result = ContentExtractor.extract_code_blocks(content)
        print(f"✓ {name}: No error")
    except Exception as e:
        print(f"✗ {name}: {type(e).__name__}: {e}")