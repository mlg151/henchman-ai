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
    block_str = blocks1[0]
    has_raw_string = 'r"isn' in block_str and "'t" in block_str
    print(f"Has raw string with apostrophe: {has_raw_string}")
    print(f"Full block: {repr(block_str[:100])}...")

# Test case: multiple string prefixes with apostrophe
content2 = '''```python
s = fr"isn't"  # Formatted raw string with apostrophe
print(s)
```'''

print("\nTesting formatted raw string with apostrophe...")
blocks2 = ContentExtractor.extract_code_blocks(content2)
print(f"Number of blocks: {len(blocks2)}")
if blocks2:
    block_str = blocks2[0]
    has_fr_string = 'fr"isn' in block_str and "'t" in block_str
    print(f"Has fr string with apostrophe: {has_fr_string}")

# Test case: apostrophe at beginning of word after string prefix
content3 = '''```python
s = r"'hello"  # Raw string starting with quote
print(s)
```'''

print("\nTesting raw string starting with quote...")
blocks3 = ContentExtractor.extract_code_blocks(content3)
print(f"Number of blocks: {len(blocks3)}")
if blocks3:
    block_str = blocks3[0]
    has_raw_string_starting_with_quote = 'r"\'hello' in block_str or 'r"\'hello' in block_str.replace('\\', '')
    print(f"Has raw string starting with quote: {has_raw_string_starting_with_quote}")

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
    print(f"Full block excerpt: {repr(block_str[50:150])}")