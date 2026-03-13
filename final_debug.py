from henchman.utils.intelligent_context import ContentExtractor

# The exact test case that's failing
# Note: We need to escape backslashes in the string literal
content = '''```python
path = r"C:\\`temp`\\file.txt"
print(path)
```'''

print('Content:', repr(content))
result = ContentExtractor.extract_code_blocks(content)
print('Number of results:', len(result))
if result:
    print('Result:', repr(result[0]))
    
    # Check for form feed
    if '\x0c' in result[0]:
        print('ERROR: Contains form feed character!')
    else:
        print('OK: No form feed character')
    
    # Check for backslash-f
    if '\\f' in result[0]:
        print('OK: Contains backslash-f')
    else:
        print('Missing backslash-f')
        
    # Show the problematic part
    import re
    match = re.search(r'file\.txt', result[0])
    if match:
        start = max(0, match.start() - 10)
        end = min(len(result[0]), match.end() + 10)
        print(f'Context around "file.txt": {repr(result[0][start:end])}')