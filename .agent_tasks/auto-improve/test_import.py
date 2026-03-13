"""Test import of intelligent_context module."""

import sys
sys.path.insert(0, '/home/matthew/mlg-cli/src')

try:
    # Try to import just the module
    import henchman.utils.intelligent_context as ic
    print("Import successful!")
    print(f"Module: {ic}")
    
    # Try to access ContentExtractor
    from henchman.utils.intelligent_context import ContentExtractor
    print(f"ContentExtractor: {ContentExtractor}")
    
    # Test the methods
    result = ContentExtractor.extract_error_sections("Test Error: something")
    print(f"extract_error_sections result: {result}")
    
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()