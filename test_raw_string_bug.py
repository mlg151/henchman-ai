#!/usr/bin/env python3
"""Test raw string backslash escaping bug."""

# Test case: r'\n"' - backslash escapes n, not quote
test_string = r'\n"'
print(f"Testing raw string: r'{test_string}'")
print(f"String literal: {repr(test_string)}")
print(f"Characters: {[repr(c) for c in test_string]}")

# The string r'\n"' contains: backslash, n, quote
# In a raw string, \n is NOT a newline, it's literal backslash+n
# The quote is not escaped, so this should be an unterminated string

try:
    exec('x = r"\\n\""')  # r'\n"'
    print(f"\nCreated successfully: {repr(x)}")
    print("Wait, this shouldn't work! The quote is not escaped.")
except SyntaxError as e:
    print(f"\nSyntaxError (expected): {e}")

# What about r'\\"' ?
print("\n\nTesting: r'\\\\\"'")
try:
    exec('x = r"\\\\\""')  # r'\\"'
    print(f"Created: {repr(x)}")
except SyntaxError as e:
    print(f"SyntaxError: {e}")

# The issue: the code counts consecutive backslashes from position i
# But what if there's a non-backslash character between the backslash and quote?
# Example: position i has backslash, i+1 has 'n', i+2 has quote
# The code would count 1 backslash (odd) and think it escapes the quote
# But actually the backslash escapes the 'n', not the quote!