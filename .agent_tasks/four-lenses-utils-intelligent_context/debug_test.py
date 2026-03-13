from henchman.utils.intelligent_context import ContentExtractor

# Test 2: Raw string with backslash-quote (should NOT escape)
# In raw strings, \" is literal backslash-quote, not escaped quote
# unless there's an odd number of backslashes before the quote
content2 = '''```python
s = r"test\\\\"  # Raw string: backslash-backslash-quote
print(s)
```'''
print('Content:', repr(content2))
blocks2 = ContentExtractor.extract_code_blocks(content2)
print('Blocks:', blocks2)
print('Number of blocks:', len(blocks2))
if blocks2:
    print('First block:', repr(blocks2[0]))