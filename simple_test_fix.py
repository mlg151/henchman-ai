"""Simple test to understand and fix the bug."""

from henchman.utils.intelligent_context import ContentExtractor

# Test 1: Simple raw string with \f
# Note: \\f in string literal means backslash-f
content1 = '''```python
s = r"\\f"
```'''
print(f"Test 1 content: {repr(content1)}")
result1 = ContentExtractor.extract_code_blocks(content1)
print(f"Test 1 result: {repr(result1[0]) if result1 else 'None'}")
print(f"Contains \\\\f? {'\\\\f' in result1[0] if result1 else False}")
print()

# Test 2: What if we actually want to test form feed in input?
# Input with actual form feed character
form_feed = '\x0c'
content2 = f'''```python
s = r"before{form_feed}after"
```'''
print(f"Test 2 content (with form feed): {repr(content2)}")
result2 = ContentExtractor.extract_code_blocks(content2)
print(f"Test 2 result: {repr(result2[0]) if result2 else 'None'}")
print()

# Test 3: Backslash-f in regular string (not raw)
# Should be interpreted as form feed
content3 = '''```python
s = "\\f"
```'''
print(f"Test 3 content (regular string): {repr(content3)}")
result3 = ContentExtractor.extract_code_blocks(content3)
print(f"Test 3 result: {repr(result3[0]) if result3 else 'None'}")
print()

# Actually, I think the bug might be simpler.
# Look at the raw string handling code again.
# When raw_string=True and we see \ followed by f:
# - Check if next char is quote (line 241): false
# - Go to line 268: else: pass
# - Don't set escape_next
# - Continue to line 440: i += 1
# So backslash is processed as normal char, then we move to f
# f is processed as normal char (escape_next is False)
# That should work!

# Unless... what if raw_string is False?
# Let me check the string prefix detection...