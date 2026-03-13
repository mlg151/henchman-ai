"""Minimal test to demonstrate a bug in extract_code_blocks."""

import sys
sys.path.insert(0, 'src')

from henchman.utils.intelligent_context import ContentExtractor

# Minimal failing case from the complex test
content = '''```python
s1 = r"\\""
```'''

print(f"Testing content:\n{content}")
print(f"Content length: {len(content)}")

blocks = ContentExtractor.extract_code_blocks(content)
print(f"Number of code blocks: {len(blocks)}")
if blocks:
    print(f"First block: {blocks[0]}")
else:
    print("No blocks extracted!")

# Let me trace through what might be happening
# r"\\"" is:
# - r prefix
# - " starts string
# - \\ is backslash (escaped in Python string literal)
# - " ends string
# - " is extra? Wait, r"\\"" has 3 quotes!
# Actually: r"\\"" 
#   r" → raw string start
#   \\ → escaped backslash (becomes \ in string)
#   " → ends string
# So string is: \

# But in the test, it's written as r"\\"" in the Python source
# which means: raw string containing \"
# When Python parses this, it sees: r" (raw string start), \\ (backslash), " (quote)
# The quote ends the string.

# However, in the extract_code_blocks function, when it sees \\ in a raw string,
# it doesn't set escape_next (correct for raw strings).
# Then it sees ", and char_was_escaped is False.
# So it thinks the quote ends the string (correct).

# But wait, there's another " after that in r"\\""!
# Actually r"\\"" has: r, ", \, \, ", "
# That's 3 quotes total. The last quote is unmatched.
# That would be a syntax error in Python!

# Actually no, let me check:
test_code = 's1 = r"\\""'
print(f"\nTesting Python eval of: {test_code}")
try:
    result = eval(test_code)
    print(f"Python evaluates to: {repr(result)}")
except SyntaxError as e:
    print(f"Syntax error: {e}")

# Let me check what the actual string should be
print("\nManual analysis:")
print("r'\\\"' in Python source means: raw string containing backslash-quote")
print("So r'\\\"' evaluates to: '\\\\\"'")
print("Which prints as: \\\"")