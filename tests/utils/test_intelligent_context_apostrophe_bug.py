"""Test for apostrophe bug in intelligent_context.py."""

import pytest

from henchman.utils.intelligent_context_extractor import ContentExtractor


def test_apostrophe_after_variable():
    """Test that a'hello' is correctly parsed as variable followed by string.

    This exposes a bug: a'hello' should be parsed as:
    - variable 'a'
    - string literal 'hello'
    Not as an apostrophe in a word.
    """
    content = '''```python
x = a'hello'
print(x)
```'''

    result = ContentExtractor.extract_code_blocks(content)
    assert len(result) == 1, f"Expected 1 code block, got {len(result)}"
    code = result[0]
    assert "x = a'hello'" in code, f"String literal after variable not preserved. Code: {code}"


def test_apostrophe_in_word_vs_string():
    """Test differentiation between apostrophe in word and string literal.

    isn't -> apostrophe in word
    a'hello' -> variable a followed by string 'hello'
    """
    content = '''```python
# Test cases
word = "isn't"  # String containing apostrophe
result = a'hello'  # Variable a followed by string
print(word, result)
```'''

    result = ContentExtractor.extract_code_blocks(content)
    assert len(result) == 1, f"Expected 1 code block, got {len(result)}"
    code = result[0]
    # Should extract the entire code block
    assert "word = \"isn't\"" in code or "word = 'isn\\'t'" in code, \
        f"String with apostrophe not preserved. Code: {code}"
    assert "result = a'hello'" in code, \
        f"String literal after variable not preserved. Code: {code}"


def test_string_prefix_with_apostrophe_after_variable():
    """Test r'hello' vs a'r'hello'.

    r'hello' -> raw string
    a'r'hello' -> variable a followed by raw string 'hello'
    """
    content = '''```python
s1 = r'hello'  # Raw string
s2 = a'r'hello'  # Variable a followed by raw string
print(s1, s2)
```'''

    result = ContentExtractor.extract_code_blocks(content)
    assert len(result) == 1, f"Expected 1 code block, got {len(result)}"
    code = result[0]
    assert "s1 = r'hello'" in code, f"Raw string not preserved. Code: {code}"
    assert "s2 = a'r'hello'" in code, f"Variable followed by raw string not preserved. Code: {code}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
