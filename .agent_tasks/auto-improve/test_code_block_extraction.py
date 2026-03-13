"""Test code block extraction functionality."""
import sys
sys.path.insert(0, 'src')

from henchman.utils.intelligent_context import ContentExtractor
import re

def test_extract_code_blocks_pattern():
    """Test the regex pattern for code block extraction."""
    # Test pattern directly
    pattern = r"```(?:\w+)?\n(.*?)\n```"
    
    # Test case 1: Code block with language and newline
    content1 = "```python\ndef hello():\n    return 'world'\n```"
    matches1 = re.findall(pattern, content1, re.DOTALL)
    print(f"Test 1 - With newline: {len(matches1)} matches")
    
    # Test case 2: Code block without newline after language
    content2 = "```python def hello():\n    return 'world'\n```"
    matches2 = re.findall(pattern, content2, re.DOTALL)
    print(f"Test 2 - Without newline: {len(matches2)} matches")
    
    # Test case 3: Code block without language
    content3 = "```\ndef hello():\n    return 'world'\n```"
    matches3 = re.findall(pattern, content3, re.DOTALL)
    print(f"Test 3 - No language: {len(matches3)} matches")
    
    # Test the actual method
    print("\nTesting ContentExtractor.extract_code_blocks:")
    
    # Test with newline
    result1 = ContentExtractor.extract_code_blocks(content1)
    print(f"Result 1: {len(result1)} blocks")
    if result1:
        print(f"Block: {result1[0][:50]}...")
    
    # Test with spaces instead of newline
    content4 = "Some text ```python\ndef test():\n    pass\n``` more text"
    result4 = ContentExtractor.extract_code_blocks(content4)
    print(f"\nResult with surrounding text: {len(result4)} blocks")
    
    return len(matches1), len(matches2), len(matches3), len(result1), len(result4)

if __name__ == "__main__":
    test_extract_code_blocks_pattern()