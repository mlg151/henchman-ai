from henchman.utils.intelligent_context import ContentExtractor

# Test with regular string with escaped quote (valid)
content1 = '''```python
s = "test\\"  # Escaped quote
print(s)
```'''
print("Test 1 - Regular string with escaped quote:")
print("Content:", repr(content1))
blocks1 = ContentExtractor.extract_code_blocks(content1)
print("Blocks:", blocks1)
print("Number of blocks:", len(blocks1))
if blocks1:
    print("First block:", repr(blocks1[0]))

# Test with raw string with even backslashes (valid)
content2 = '''```python
s = r"test\\\\"  # Even backslashes
print(s)
```'''
print("\nTest 2 - Raw string with even backslashes:")
print("Content:", repr(content2))
blocks2 = ContentExtractor.extract_code_blocks(content2)
print("Blocks:", blocks2)
print("Number of blocks:", len(blocks2))
if blocks2:
    print("First block:", repr(blocks2[0]))

# Test with raw string with odd backslashes (invalid - unterminated)
content3 = '''```python
s = r"test\\\\\\"  # Odd backslashes - syntax error
print(s)
```'''
print("\nTest 3 - Raw string with odd backslashes (syntax error):")
print("Content:", repr(content3))
blocks3 = ContentExtractor.extract_code_blocks(content3)
print("Blocks:", blocks3)
print("Number of blocks:", len(blocks3))
if blocks3:
    print("First block:", repr(blocks3[0]))