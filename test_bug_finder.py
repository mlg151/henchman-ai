import sys
sys.path.insert(0, 'src')

from henchman.utils.intelligent_context import _ParserState

# Create a parser state
state = _ParserState()

# Test the _is_valid_string_prefix method if it exists
if hasattr(state, '_is_valid_string_prefix'):
    print("Testing _is_valid_string_prefix:")
    test_prefixes = ['r', 'u', 'b', 'f', 'br', 'rb', 'fr', 'rf', 'ur', 'ru', 'fb', 'bf', 'rr', 'bb', 'ff', 'uu']
    for prefix in test_prefixes:
        try:
            result = state._is_valid_string_prefix(prefix)
            print(f"  _is_valid_string_prefix('{prefix}') = {result}")
        except Exception as e:
            print(f"  _is_valid_string_prefix('{prefix}') raised {type(e).__name__}: {e}")

# Now test _is_apostrophe_in_word with edge cases
print("\nTesting _is_apostrophe_in_word edge cases:")

# Test case that might trigger the bug: string prefix detection
test_cases = [
    # (text, i, description)
    ("r'hello'", 1, "Raw string prefix r'"),
    ("u'hello'", 1, "Unicode string prefix u'"),
    ("b'hello'", 1, "Bytes string prefix b'"),
    ("f'hello'", 1, "Formatted string prefix f'"),
    ("br'hello'", 2, "Bytes raw string prefix br'"),
    ("fr'hello'", 2, "Formatted raw string prefix fr'"),
    ("rf'hello'", 2, "Raw formatted string prefix rf'"),
    ("rb'hello'", 2, "Raw bytes string prefix rb'"),
    ("ur'hello'", 2, "Unicode raw string prefix ur' (Python 2 style)"),
    ("RU'hello'", 2, "Uppercase prefix RU'"),
    ("F'hello'", 1, "Uppercase F prefix"),
    ("variable'hello", 8, "Apostrophe after variable name (should be False)"),
    ("don't", 3, "Normal apostrophe"),
    ("can't", 3, "Normal apostrophe"),
    ("won't", 3, "Normal apostrophe"),
    ("it's", 2, "Apostrophe in it's"),
    ("that's", 4, "Apostrophe in that's"),
]

for text, i, desc in test_cases:
    try:
        result = state._is_apostrophe_in_word(text, i)
        print(f"  {desc:50} _is_apostrophe_in_word('{text}', {i}) = {result}")
    except Exception as e:
        print(f"  {desc:50} _is_apostrophe_in_word('{text}', {i}) raised {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()