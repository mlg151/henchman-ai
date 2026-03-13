#!/usr/bin/env python3
"""Debug the parser."""

import sys
sys.path.insert(0, 'src')

from henchman.utils.intelligent_context import _ParserState

# Create a simple test
text = '''s = "hello\\
```world"
print(s)'''

print(f"Testing text: {repr(text)}")
print(f"Length: {len(text)}")

# Create parser state
state = _ParserState()

# Manually simulate parsing
print("\nManual simulation:")
for i, char in enumerate(text):
    was_escaped = False  # Simplified
    print(f"Position {i}: char={repr(char)}, in_string={state.in_string}, string_char={state.string_char}, triple_quote={state.triple_quote}")
    
    # Simulate _process_char logic for newline
    if char == "\n":
        print(f"  Newline! in_string={state.in_string}, not triple_quote={not state.triple_quote}")
        if state.in_string and not state.triple_quote:
            print(f"  Would end string (BUG: doesn't check for line continuation)")
            # state.in_string = False
            # state.string_char = None
            # etc.
    
    # Simulate string start
    if not state.in_string and char == '"' and not was_escaped:
        print(f"  Would start string at position {i}")

print("\nActual Python interpretation:")
print(f"String value: {repr(eval(text.split('=')[1].strip()))}")