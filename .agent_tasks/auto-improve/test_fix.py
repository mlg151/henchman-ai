"""Test script to understand the intelligent_context.py issue."""

# Let me examine the actual error
import sys
sys.path.insert(0, '/home/matthew/mlg-cli/src')

try:
    from henchman.utils.intelligent_context import ContentExtractor
    print("Import successful!")
    print(f"extract_error_sections type: {type(ContentExtractor.extract_error_sections)}")
    print(f"extract_tool_sections type: {type(ContentExtractor.extract_tool_sections)}")
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()