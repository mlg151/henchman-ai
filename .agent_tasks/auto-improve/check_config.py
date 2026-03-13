#!/usr/bin/env python3
"""Check if IntelligentContextManager has config attribute."""

import sys
sys.path.insert(0, 'src')

from henchman.utils.intelligent_context import IntelligentContextManager

m = IntelligentContextManager()
print(f"Has config attribute: {hasattr(m, 'config')}")
print(f"Config value: {getattr(m, 'config', 'NO CONFIG ATTRIBUTE')}")
print(f"All attributes starting with 'c': {[a for a in dir(m) if a.startswith('c')]}")