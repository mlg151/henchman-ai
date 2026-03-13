#!/usr/bin/env python3
"""Test for apostrophe vs string prefix bug at beginning of text."""

# Test cases
test_cases = [
    "r'hello'",      # r' at beginning
    "x = r'hello'",  # r' after space
    "x=r'hello'",    # r' after =
    "(r'hello')",    # r' after (
]

for text in test_cases:
    i = text.find("'")  # Position of the quote
    print(f"\nText: {text}")
    print(f"Quote position i: {i}")
    
    # Simulate the logic from _is_apostrophe_in_word
    j = i - 1
    while j >= 0 and text[j].lower() in ("r", "u", "b", "f"):
        j -= 1

    print(f"After while loop: j = {j}")
    print(f"Condition: j < i - 1 ? {j} < {i-1} = {j < i - 1}")
    
    if j < i - 1:
        print("Would check prefix")
        prefix_start = j + 1
        prefix = text[prefix_start:i].lower()
        print(f"Prefix: '{prefix}'")
    else:
        print("Would NOT check prefix")
        if j == i - 1:
            print("  BUG: Single character prefix 'r' not checked!")