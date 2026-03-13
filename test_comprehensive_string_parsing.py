#!/usr/bin/env python3
"""Comprehensive test for string parsing bugs."""

from henchman.utils.intelligent_context import ContentExtractor

# Test cases that might expose bugs
test_cases = [
    # (name, content, expected_blocks)
    ("Empty string ''", '''```python\ns = ''\n```''', 1),
    ("String with apostrophe", '''```python\ns = "isn't"\n```''', 1),
    ("Escaped quote", '''```python\ns = "he said \\"hello\\""\n```''', 1),
    ("Raw string with backslashes", '''```python\ns = r"\\\\"\n```''', 1),
    ("Triple-quoted string", '''```python\ns = """hello\nworld"""\n```''', 1),
    ("String with backticks", '''```python\ns = "`code`"\n```''', 1),
    ("Multiple strings with backticks", '''```python\ns = "`a`"; t = "`b`"\n```''', 1),
    ("Code block with string containing ```", '''```python\ns = "```"\n```''', 1),
    ("Nested: code block inside string in code block", '''```python\nprint("```python\nprint(1)\n```")\n```''', 1),
]

print("Running comprehensive string parsing tests...")
all_pass = True

for name, content, expected in test_cases:
    result = ContentExtractor.extract_code_blocks(content)
    passed = len(result) == expected
    if not passed:
        print(f"✗ {name}: expected {expected} blocks, got {len(result)}")
        print(f"  Content: {repr(content)}")
        print(f"  Result: {result}")
        all_pass = False
    else:
        print(f"✓ {name}")

# Special test: code block with string that has ``` inside
print("\nSpecial test: Code block with string containing ```")
content = '''Some text
```python
s = "This string contains ``` markers"
print(s)
```
More text'''
result = ContentExtractor.extract_code_blocks(content)
if len(result) == 1:
    print("✓ Correctly extracted 1 code block")
else:
    print(f"✗ Expected 1 block, got {len(result)}")
    all_pass = False

if all_pass:
    print("\nAll tests passed (no bug found)")
else:
    print("\nSome tests failed - bug found!")