"""Test complex apostrophe detection bug."""
from henchman.utils.intelligent_context import ContentExtractor

# Test case: string prefix followed by apostrophe in word
# e.g., r"isn't" - the ' is inside the string, not an apostrophe in code
content1 = '''```python
s = r"isn't"  # Raw string with apostrophe
print(s)
```'''

print("Testing raw string with apostrophe...")
blocks1 = ContentExtractor.extract_code_blocks(content1)
print(f"Number of blocks: {len(blocks1)}")
if blocks1:
    print(f"Block contains r\"isn't\": {'r\"isn\\'t\"' in blocks1[0] or 'r\"isn\'t\"' in blocks1[0]}")

# Test case: multiple string prefixes with apostrophe
content2 = '''```python
s = fr"isn't"  # Formatted raw string with apostrophe
print(s)
```'''

print("\nTesting formatted raw string with apostrophe...")
blocks2 = ContentExtractor.extract_code_blocks(content2)
print(f"Number of blocks: {len(blocks2)}")
if blocks2:
    print(f"Block contains fr\"isn't\": {'fr\"isn\\'t\"' in blocks2[0] or 'fr\"isn\'t\"' in blocks2[0]}")

# Test case: apostrophe at beginning of word after string prefix
content3 = '''```python
s = r"'hello"  # Raw string starting with quote
print(s)
```'''

print("\nTesting raw string starting with quote...")
blocks3 = ContentExtractor.extract_code_blocks(content3)
print(f"Number of blocks: {len(blocks3)}")
if blocks3:
    print(f"Block contains r\"'hello\": {'r\"\\'hello\"' in blocks3[0] or 'r\"\'hello\"' in blocks3[0]}")

# Test case: complex string with escaped quote and apostrophe
content4 = '''```python
s = "He said \\"isn't that right?\\""  # Escaped quote and apostrophe
print(s)
```'''

print("\nTesting complex string with escaped quote and apostrophe...")
blocks4 = ContentExtractor.extract_code_blocks(content4)
print(f"Number of blocks: {len(blocks4)}")
if blocks4:
    # Check if the string is preserved correctly
    block_str = blocks4[0]
    has_escaped_quote = '\\"' in block_str
    has_apostrophe = "isn't" in block_str
    print(f"Has escaped quote: {has_escaped_quote}")
    print(f"Has apostrophe: {has_apostrophe}")