"""Test with valid Python syntax."""

import sys
sys.path.insert(0, 'src')

from henchman.utils.intelligent_context import ContentExtractor

# Test with valid Python syntax
content1 = '''```python
s1 = r"\\""  # This is actually invalid! r"\\"" has 3 quotes
```'''

content2 = '''```python
s1 = r"\\\\""  # This is r"\\" followed by " - also invalid!
```'''

content3 = '''```python
s1 = r"\\\\\\""  # r"\\\" - raw string with backslash-quote
```'''

content4 = '''```python
s1 = "\\""  # Regular string with escaped quote
```'''

content5 = '''```python
s1 = r"\\"  # Raw string with backslash (valid)
```'''

for i, content in enumerate([content1, content2, content3, content4, content5], 1):
    print(f"\n=== Testing content{i} ===")
    print(f"Content: {repr(content)}")
    blocks = ContentExtractor.extract_code_blocks(content)
    print(f"Blocks extracted: {len(blocks)}")
    if blocks:
        print(f"Block: {repr(blocks[0])}")

# Actually, let me think about what the REAL bug might be.
# Looking at the code again, I notice something in the backtick counting logic:

print("\n\nAnalyzing the actual bug...")
print("In the function, when char == '`' and not char_was_escaped:")
print("It checks if content[i:i+3] == '```'")
print("If yes, it checks if preceded_by_newline_or_start = i == 0 or content[i-1] == '\\n'")
print("If preceded_by_newline_or_start OR (i + 3 == content_length) OR backtick_count > 0:")
print("  if not in_string: backtick_count += 1")
print("  else: backtick_count = 0")
print("else: backtick_count = 0")
print("\nThe bug might be in the 'else: backtick_count = 0' at line ~285")
print("This resets backtick_count even when we're NOT looking at triple backticks!")
print("So if we see a single backtick in code, it resets the count.")
print("But we might be in the middle of counting closing backticks!")
print("Actually, that's at line 285: 'else: backtick_count = 0'")
print("And at line 291: 'else: backtick_count = 0'")
print("And at line 293: 'else: backtick_count = 0'")
print("\nWait, line 293 is: 'else: backtick_count = 0'")
print("This is OUTSIDE the 'if char == '`' and not char_was_escaped:' block!")
print("So ANY character that's not a backtick resets backtick_count!")
print("That means: '```some text```' would work")
print("But: '```text with ` in it```' would fail!")
print("Because the ` in the middle would reset backtick_count to 0!")
print("\nTHAT'S THE BUG!")