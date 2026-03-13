"""Test to understand the escaped character bug."""
from henchman.utils.intelligent_context import ContentExtractor

# Test case from the test file
content1 = '''```python
s = "test\\"s value"  # Escaped quote followed by 's
print(s)
```'''

print("Testing escaped quote in regular string...")
blocks1 = ContentExtractor.extract_code_blocks(content1)
print(f"Number of blocks: {len(blocks1)}")
if blocks1:
    print(f"Block content: {repr(blocks1[0])}")
    if '"test\\"s value"' in blocks1[0]:
        print("✓ Escaped quote preserved correctly")
    else:
        print("✗ Escaped quote NOT preserved!")

# Test with escaped backtick
content2 = '''```python
s = "test\\`s value"  # Escaped backtick
print(s)
```'''

print("\nTesting escaped backtick in string...")
blocks2 = ContentExtractor.extract_code_blocks(content2)
print(f"Number of blocks: {len(blocks2)}")
if blocks2:
    print(f"Block content: {repr(blocks2[0])}")
    if '"test\\`s value"' in blocks2[0]:
        print("✓ Escaped backtick preserved correctly")
    else:
        print("✗ Escaped backtick NOT preserved!")

# Test with multiple escaped characters
content3 = '''```python
s = "test\\"\\`\\'s value"  # Multiple escaped characters
print(s)
```'''

print("\nTesting multiple escaped characters...")
blocks3 = ContentExtractor.extract_code_blocks(content3)
print(f"Number of blocks: {len(blocks3)}")
if blocks3:
    print(f"Block content: {repr(blocks3[0])}")