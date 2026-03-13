import sys
sys.path.insert(0, 'src')

from henchman.utils.intelligent_context import _ParserState

state = _ParserState()

# Test cases that might expose bugs
test_cases = [
    # (text, i, expected, description)
    ("", 0, False, "Empty string"),
    ("", -1, False, "Empty string, negative index"),
    ("", 1, False, "Empty string, out of bounds"),
    ("a", 0, False, "Single char, not quote"),
    ("'", 0, False, "Single quote"),
    ("'", -1, False, "Single quote, negative index"),
    ("''", 0, False, "Two quotes, first at position 0"),
    ("''", 1, False, "Two quotes, second at position 1"),
    ("a'", 1, False, "Quote at end, not contraction"),
    ("'a", 0, False, "Quote at start"),
    ("don't", 3, True, "Valid contraction don't"),
    ("don't.", 3, True, "Contraction with period after"),
    ("don't worry", 3, True, "Contraction in middle"),
    ("(don't)", 4, True, "Contraction in parentheses"),
    ["don't", -2, True, "Contraction with negative index (position 3 = -2)"],  # "don't" length 5, position 3 = -2
    ("DON'T", 3, True, "Uppercase contraction"),
    ("Don't", 3, True, "Capitalized contraction"),
    ("dOn'T", 3, True, "Mixed case contraction"),
    ("can't", 3, True, "can't"),
    ("won't", 3, True, "won't"),
    ("shan't", 4, True, "shan't (apostrophe at position 4)"),
    ("it's", 2, True, "it's"),
    ("that's", 4, True, "that's"),
    ("they're", 5, True, "they're (apostrophe at position 5)"),
    ("we've", 3, True, "we've"),
    ("I'd", 1, True, "I'd"),
    ("I'm", 1, True, "I'm"),
    ("you'll", 4, True, "you'll"),
    ("he'll", 3, True, "he'll"),
    ("she'll", 4, True, "she'll"),
    ("it'll", 3, True, "it'll"),
    ("we'll", 3, True, "we'll"),
    ("they'll", 5, True, "they'll"),
    ("could've", 6, True, "could've"),
    ("should've", 7, True, "should've"),
    ("would've", 6, True, "would've"),
    ("might've", 6, True, "might've"),
    ("must've", 5, True, "must've"),
    ("r'hello'", 1, False, "Raw string prefix"),
    ("R'hello'", 1, False, "Uppercase raw string prefix"),
    ("u'hello'", 1, False, "Unicode string prefix"),
    ("b'hello'", 1, False, "Bytes string prefix"),
    ("f'hello'", 1, False, "Formatted string prefix"),
    ("br'hello'", 2, False, "Bytes raw string prefix"),
    ("fr'hello'", 2, False, "Formatted raw string prefix"),
    ("rf'hello'", 2, False, "Raw formatted string prefix"),
    ("rb'hello'", 2, False, "Raw bytes string prefix"),
    ("ur'hello'", 2, False, "Unicode raw string prefix (Python 2)"),
    ("rr'hello'", 2, False, "Invalid prefix rr'"),
    ("bb'hello'", 2, False, "Invalid prefix bb'"),
    ("ff'hello'", 2, False, "Invalid prefix ff'"),
    ("uu'hello'", 2, False, "Invalid prefix uu'"),
    ("variable'value", 8, False, "Not a contraction, apostrophe in identifier"),
    ("word'_suffix", 4, False, "Apostrophe with underscore after"),
    ("word'123", 4, False, "Apostrophe with digits after"),
    ("word'.txt", 4, False, "Apostrophe with dot after"),
    ("a'hello", 1, False, "Single letter before apostrophe, not contraction"),
    ("qb'll", 2, False, "qb'll - not a valid contraction"),
    ("z're", 1, False, "z're - not a valid contraction"),
    ("p's", 1, False, "p's - not a valid contraction"),
    ("x'd", 1, False, "x'd - not a valid contraction"),
    ("y've", 1, False, "y've - not a valid contraction"),
    ("w'm", 1, False, "w'm - not a valid contraction"),
    ("v'll", 1, False, "v'll - not a valid contraction"),
    # Edge case: what if text[i-1] doesn't exist? i=0 after negative conversion
    ("'hello", -6, False, "Quote at start with negative index i=-len(text)"),
    # Test with unicode
    ("café's", 4, True, "Contraction with accented character before"),
    ("🇫🇷's", 2, False, "Flag emoji before quote (might fail on isalpha check)"),
    # Test with surrogate pairs or combining characters
    ("cafe\u0301's", 5, True, "Contraction with combining acute accent"),
]

print("Testing _is_apostrophe_in_word edge cases:")
for test in test_cases:
    if isinstance(test, list):
        text, i, expected, desc = test
    else:
        text, i, expected, desc = test
    
    try:
        result = state._is_apostrophe_in_word(text, i)
        status = "✓" if result == expected else "✗"
        print(f"{status} {desc:60} text='{text}', i={i:2}, expected={expected}, got={result}")
        if result != expected:
            print(f"  MISMATCH!")
    except Exception as e:
        print(f"✗ {desc:60} text='{text}', i={i:2} RAISED {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()