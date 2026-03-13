"""Test to understand the duplicate code issue in intelligent_context.py"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

# Try to import the methods that are reported as duplicates
try:
    # These should not exist at module level
    from henchman.utils.intelligent_context import from_params
    print("ERROR: from_params exists at module level!")
except ImportError:
    print("GOOD: from_params is not at module level")

try:
    from henchman.utils.intelligent_context import _create_from_params
    print("ERROR: _create_from_params exists at module level!")
except ImportError:
    print("GOOD: _create_from_params is not at module level")

try:
    from henchman.utils.intelligent_context import _get_value_or_default
    print("ERROR: _get_value_or_default exists at module level!")
except ImportError:
    print("GOOD: _get_value_or_default is not at module level")

# Check the actual imports
print("\nChecking imports from intelligent_context_config.py:")
from henchman.utils.intelligent_context_config import (
    IntelligentContextConfig,
    IntelligentContextParams
)
print(f"Imported IntelligentContextConfig: {IntelligentContextConfig}")
print(f"Imported IntelligentContextParams: {IntelligentContextParams}")

# Check if the commented class has any methods
print("\nChecking for commented class methods...")
import inspect
import henchman.utils.intelligent_context as ic_module

# Look for the methods that should not exist
for name, obj in inspect.getmembers(ic_module):
    if name in ['from_params', '_create_from_params', '_get_value_or_default']:
        print(f"FOUND: {name} = {obj}")