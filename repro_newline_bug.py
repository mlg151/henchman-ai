from henchman.utils.intelligent_context import ContentExtractor

def test_repro():
    # content with literal newline inside a string followed by 3 backticks
    content = '''```python
text = "Line1\nLine2"
x = ```backticks```
print(text)
```'''
    result = ContentExtractor.extract_code_blocks(content)
    print(f"Number of blocks: {len(result)}")
    if result:
        print(f"Block 0 (raw content): {repr(result[0])}")
    
    # Let's see if the string terminated correctly at the newline
    # If so, the parser should be in "normal" mode and find the 3 backticks as a fence.
    
    # content with escaped newline (backslash-n)
    content2 = r'''```python
text = "Line1\nLine2"
x = ```backticks```
print(text)
```'''
    result2 = ContentExtractor.extract_code_blocks(content2)
    print(f"Number of blocks (raw): {len(result2)}")
    if result2:
        print(f"Block 0 (raw content): {repr(result2[0])}")

if __name__ == "__main__":
    test_repro()
