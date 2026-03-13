"""Test to expose escaped backslash bug."""
from henchman.utils.intelligent_context import ContentExtractor

# Test with escaped backslash followed by quote: \\"
# In Python, \\" means: \ (escaped backslash) followed by " (regular quote)
# So the quote is NOT escaped!
content1 = '''```python
s = "test\\\\"  # Escaped backslash followed by quote
print(s)
```'''

print("Testing escaped backslash followed by quote...")
blocks1 = ContentExtractor.extract_code_blocks(content1)
print(f"Number of blocks: {len(blocks1)}")
if blocks1:
    print(f"Block content: {repr(blocks1[0])}")
    # Should be "test\\" (backslash then quote, quote ends string)
    if '"test\\\\"' in blocks1[0]:
        print("✓ String ends at quote (correct)")
    else:
        print("✗ Bug: String might not end correctly")

# Test with triple backslash: \\\"
# In Python, \\\" means: \ (escaped backslash) followed by \" (escaped quote)
# So the quote IS escaped!
content2 = '''```python
s = "test\\\\\\"  # Escaped backslash followed by escaped quote
print(s)
```'''

print("\nTesting escaped backslash followed by escaped quote...")
blocks2 = ContentExtractor.extract_code_blocks(content2)
print(f"Number of blocks: {len(blocks2)}")
if blocks2:
    print(f"Block content: {repr(blocks2[0])}")
    # Should be "test\\\" (backslash then escaped quote, string continues)
    if '"test\\\\\\"' in blocks2[0]:
        print("✓ Quote is escaped (correct)")
    else:
        print("✗ Bug: Quote might not be escaped correctly")

# Test with backtick inside escaped context
content3 = '''```python
s = "test\\`"  # Escaped backtick
print(s)
```'''

print("\nTesting escaped backtick in string...")
blocks3 = ContentExtractor.extract_code_blocks(content3)
print(f"Number of blocks: {len(blocks3)}")
if blocks3:
    print(f"Block content: {repr(blocks3[0])}")
    # The backtick should be escaped, not count as fence
    if '"test\\`"' in blocks3[0]:
        print("✓ Backtick is escaped (correct)")
    else:
        print("✗ Bug: Backtick might not be escaped correctly")