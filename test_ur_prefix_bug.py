"""Test ur prefix bug in Python 3."""
from henchman.utils.intelligent_context import ContentExtractor

# Test 1: ur prefix in Python 3 (should be invalid)
content1 = '''```python
s = ur"test"  # Invalid in Python 3
print(s)
```'''

print("Testing ur prefix (invalid in Python 3)...")
blocks1 = ContentExtractor.extract_code_blocks(content1)
print(f"Number of blocks: {len(blocks1)}")
if blocks1:
    print(f"Block contains ur\"test\": {'ur\"test\"' in blocks1[0]}")
    # The parser might incorrectly extract this as a code block
    # even though it's invalid Python 3

# Test 2: ru prefix (also invalid)
content2 = '''```python
s = ru"test"  # Invalid in Python 3
print(s)
```'''

print("\nTesting ru prefix (invalid in Python 3)...")
blocks2 = ContentExtractor.extract_code_blocks(content2)
print(f"Number of blocks: {len(blocks2)}")
if blocks2:
    print(f"Block contains ru\"test\": {'ru\"test\"' in blocks2[0]}")

# Test 3: What happens with ur followed by apostrophe?
content3 = '''```python
# ur' might be parsed as string prefix
x = ur'  # Invalid
```'''

print("\nTesting ur' (invalid prefix with single quote)...")
blocks3 = ContentExtractor.extract_code_blocks(content3)
print(f"Number of blocks: {len(blocks3)}")

# Actually test if Python 3 accepts ur""
import subprocess
test_code = '''
try:
    exec('s = ur"test"')
    print("ur\\"test\\" is accepted (unexpected)")
except SyntaxError as e:
    print(f"ur\\"test\\" raises SyntaxError: {e}")
'''

print("\nActual Python 3 test:")
result = subprocess.run(['python3', '-c', test_code], capture_output=True, text=True)
print(result.stdout)
if result.stderr:
    print(f"Stderr: {result.stderr}")