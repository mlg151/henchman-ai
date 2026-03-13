from henchman.utils.intelligent_context import ContentExtractor

# Revert my change first
print("Testing with original code...")

content = '''```python
path = r"C:\\\\Users\\\\test"
```'''

print(f"Input: {repr(content)}")
result = ContentExtractor.extract_code_blocks(content)
print(f"Number of results: {len(result)}")
if result:
    print(f"Result: {repr(result[0])}")
    print(f"Result string: {result[0]}")
    
    # Check what's actually in the string
    print("\nAnalyzing result...")
    # Find the path assignment
    import re
    match = re.search(r'path = (r?"[^"]*")', result[0])
    if match:
        path_str = match.group(1)
        print(f"Extracted path string: {path_str}")
        print(f"Repr of path string: {repr(path_str)}")
        print(f"Length: {len(path_str)}")
        print(f"Characters:")
        for i, ch in enumerate(path_str):
            print(f"  {i}: {repr(ch)}")