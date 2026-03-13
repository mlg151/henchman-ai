"""Test invalid string prefix bug."""
from henchman.utils.intelligent_context import ContentExtractor

# Test 1: Invalid prefix 'ur' (not valid in Python 3)
# The parser might incorrectly treat 'ur' as a string prefix
# and start a string at the quote, when it should treat the quote
# as an apostrophe in a word like "ur" (which isn't a word, but still)
content1 = '''```python
# ur"string" would be invalid Python 3
# but ur might appear as part of a word
x = ur"  # This is invalid Python 3
```'''

print("Testing invalid 'ur' prefix...")
blocks1 = ContentExtractor.extract_code_blocks(content1)
print(f"Number of blocks: {len(blocks1)}")
if blocks1:
    print(f"Block: {repr(blocks1[0][:100])}...")

# Test 2: Invalid prefix 'rr' (duplicate r)
content2 = '''```python
# rr"string" is invalid
x = rr"test"
```'''

print("\nTesting invalid 'rr' prefix...")
blocks2 = ContentExtractor.extract_code_blocks(content2)
print(f"Number of blocks: {len(blocks2)}")
if blocks2:
    print(f"Block: {repr(blocks2[0][:100])}...")

# Test 3: What should happen with 'ur' followed by apostrophe?
# e.g., "ur'" - is this a string starting with ' or an apostrophe in "ur'"?
content3 = '''```python
# This is tricky: ur' might be parsed as invalid string prefix
# or as word "ur" followed by apostrophe
x = ur'  # What should happen here?
```'''

print("\nTesting 'ur' followed by apostrophe...")
blocks3 = ContentExtractor.extract_code_blocks(content3)
print(f"Number of blocks: {len(blocks3)}")
if blocks3:
    print(f"Block: {repr(blocks3[0][:100])}...")

# Test 4: Valid prefix 'br' should work
content4 = '''```python
# br is valid (bytes raw)
x = br"test"
```'''

print("\nTesting valid 'br' prefix (control test)...")
blocks4 = ContentExtractor.extract_code_blocks(content4)
print(f"Number of blocks: {len(blocks4)}")
if blocks4:
    print(f"Block contains br\"test\": {'br\"test\"' in blocks4[0]}")