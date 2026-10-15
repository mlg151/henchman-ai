"""Tests for intelligent context management."""

import pytest

from henchman.utils.intelligent_context import (
    ContentExtractor,
)


def test_extract_code_blocks_empty():
    """Test extracting code blocks from empty content."""
    result = ContentExtractor.extract_code_blocks("")
    assert result == []


def test_extract_code_blocks_single_block():
    """Test extracting a single code block."""
    content = """Some text before
```python
def hello():
    return "world"
```
Some text after"""
    result = ContentExtractor.extract_code_blocks(content)
    assert len(result) == 1
    assert "def hello():" in result[0]
    assert 'return "world"' in result[0]


def test_extract_code_blocks_multiple_blocks():
    """Test extracting multiple code blocks."""
    content = """First block:
```python
print("hello")
```

Second block:
```bash
ls -la
```"""
    result = ContentExtractor.extract_code_blocks(content)
    assert len(result) == 2
    assert 'print("hello")' in result[0]
    assert "ls -la" in result[1]


def test_extract_code_blocks_no_blocks():
    """Test extracting code blocks when none exist."""
    content = "Just some regular text without code blocks."
    result = ContentExtractor.extract_code_blocks(content)
    assert result == []


def test_extract_code_blocks_nested_backticks():
    """Test extracting code blocks with nested backticks inside strings."""
    content = '''```python
print("`hello`")
```'''
    result = ContentExtractor.extract_code_blocks(content)
    assert len(result) == 1
    assert 'print("`hello`")' in result[0]


def test_extract_code_blocks_raw_string_backslash_bug():
    """Test extracting code blocks with raw strings containing backslashes.

    This test verifies that raw string handling correctly preserves backslashes.
    """
    content = '''```python
# Raw string with backslashes
path = r"C:\\\\Users\\\\test"
print(path)
```'''
    result = ContentExtractor.extract_code_blocks(content)
    assert len(result) == 1
    # Note: r"C:\\Users\\test" in Python source prints as r"C:\Users\test"
    # because \\ in a raw string is a literal backslash
    assert r'C:\\Users\\test' in result[0], f"Raw string with backslashes not preserved: {result[0]}"


def test_extract_code_blocks_empty_code_blocks():
    """Test extracting empty code blocks.

    This test exposes a bug where empty code blocks are not extracted.
    """
    # Test 1: Empty code block with no content - 6 backticks is NOT a valid code block
    # because there's no newline between opening and closing fences
    content1 = '``````'
    blocks1 = ContentExtractor.extract_code_blocks(content1)
    # 6 consecutive backticks is not a valid code block
    assert len(blocks1) == 0, f"6 backticks should not be a code block: expected 0, got {len(blocks1)}"

    # Test 2: Empty code block with newlines
    content2 = '```\n```'
    blocks2 = ContentExtractor.extract_code_blocks(content2)
    assert len(blocks2) == 1, f"Empty code block with newlines not extracted: expected 1, got {len(blocks2)}"

    # Test 3: Empty code block with language
    content3 = '```python\n```'
    blocks3 = ContentExtractor.extract_code_blocks(content3)
    assert len(blocks3) == 1, f"Empty code block with language not extracted: expected 1, got {len(blocks3)}"
    assert 'python' in blocks3[0], f"Language not preserved in empty code block: {blocks3[0]}"

    # Test 4: Code block with only whitespace
    content4 = '```   \n   \n   ```'
    blocks4 = ContentExtractor.extract_code_blocks(content4)
    assert len(blocks4) == 1, f"Code block with only whitespace not extracted: expected 1, got {len(blocks4)}"


def test_extract_code_blocks_combined_string_prefixes():
    """Test that combined string prefixes (br, rb, fr, rf) are recognized as raw strings.

    This test exposes a bug where combined prefixes like br" are not recognized
    as raw strings, causing incorrect backslash handling.
    """
    # Test 1: br prefix (bytes raw string)
    content1 = '''```python
data = br"Hello\\nWorld"  # Should be raw: backslash-n, not newline
print(data)
```'''
    blocks1 = ContentExtractor.extract_code_blocks(content1)
    assert len(blocks1) == 1, f"Expected 1 code block, got {len(blocks1)}"
    # The source should preserve double backslash (\\ in source becomes \ in string)
    assert 'br"Hello\\nWorld"' in blocks1[0], f"br string not preserved correctly: {blocks1[0]}"

    # Test 2: rb prefix (raw bytes string) - same as br
    content2 = '''```python
data = rb"Hello\\nWorld"
print(data)
```'''
    blocks2 = ContentExtractor.extract_code_blocks(content2)
    assert len(blocks2) == 1, f"Expected 1 code block, got {len(blocks2)}"
    assert 'rb"Hello\\nWorld"' in blocks2[0], f"rb string not preserved correctly: {blocks2[0]}"

    # Test 3: fr prefix (formatted raw string)
    content3 = '''```python
name = "world"
msg = fr"Hello {name}\\n"  # Raw f-string: backslash-n literal
print(msg)
```'''
    blocks3 = ContentExtractor.extract_code_blocks(content3)
    assert len(blocks3) == 1, f"Expected 1 code block, got {len(blocks3)}"
    assert 'fr"Hello {name}\\n"' in blocks3[0], f"fr string not preserved correctly: {blocks3[0]}"

    # Test 4: rf prefix (raw formatted string) - same as fr
    content4 = '''```python
name = "world"
msg = rf"Hello {name}\\n"
print(msg)
```'''
    blocks4 = ContentExtractor.extract_code_blocks(content4)
    assert len(blocks4) == 1, f"Expected 1 code block, got {len(blocks4)}"
    assert 'rf"Hello {name}\\n"' in blocks4[0], f"rf string not preserved correctly: {blocks4[0]}"

    # Test 5: Triple-quoted raw string with prefix
    content5 = '''```python
doc = br"""Hello\\nWorld"""
print(doc)
```'''
    blocks5 = ContentExtractor.extract_code_blocks(content5)
    assert len(blocks5) == 1, f"Expected 1 code block, got {len(blocks5)}"
    assert 'br"""Hello\\nWorld"""' in blocks5[0], f"Triple-quoted br string not preserved: {blocks5[0]}"


def test_extract_code_blocks_four_backticks():
    """Test extracting code blocks with 4 backticks (Markdown allows ≥3).

    This test exposes a bug where extra backticks are included in code content.
    """
    # Test 1: 4 backticks with language
    content1 = '````python\nprint("hello")\n````'
    blocks1 = ContentExtractor.extract_code_blocks(content1)
    assert len(blocks1) == 1, f"Expected 1 code block, got {len(blocks1)}"
    # Should not have extra backtick in code
    block1 = blocks1[0]
    # Check that code doesn't start with backtick-python
    if '```python' in block1:
        # Language correctly identified
        code_start = block1.find('```python\n') + 10
        code = block1[code_start:-3]
        assert '`python' not in code, f"Extra backtick in code: {code[:50]}"
    else:
        # Language not identified, check code doesn't start with backtick
        code_start = block1.find('```\n') + 4
        code = block1[code_start:-3]
        assert not code.startswith('`python'), f"Code starts with backtick: {code[:50]}"

    # Test 2: 4 backticks without language
    content2 = '````\nprint("hello")\n````'
    blocks2 = ContentExtractor.extract_code_blocks(content2)
    assert len(blocks2) == 1, f"Expected 1 code block, got {len(blocks2)}"
    block2 = blocks2[0]
    # Code should be 'print("hello")' not start with backtick
    code_start2 = block2.find('```\n') + 4
    code2 = block2[code_start2:-3]
    assert not code2.startswith('`'), f"Code starts with backtick: {code2[:50]}"


def test_extract_code_blocks_carriage_return_line_ending():
    """Test extracting code blocks preceded by carriage return (\r) line ending.

    This test verifies that code blocks after \r are recognized.
    """
    # Test with \r (old Mac line ending)
    content = 'Some text\r```python\nprint("hello")\n```'
    result = ContentExtractor.extract_code_blocks(content)
    assert len(result) == 1, f"Code block after \\r not extracted: expected 1, got {len(result)}"

    # Test with \r\n (Windows) - should work
    content2 = 'Some text\r\n```python\nprint("hello")\n```'
    result2 = ContentExtractor.extract_code_blocks(content2)
    assert len(result2) == 1, f"Code block after \\r\\n not extracted: expected 1, got {len(result2)}"

    # Test with \n (Unix) - should work
    content3 = 'Some text\n```python\nprint("hello")\n```'
    ContentExtractor.extract_code_blocks(content3)


def test_extract_code_blocks_raw_string_double_backslash():
    """Test extracting code blocks with raw strings containing double backslashes.

    This test exposes a bug where code blocks with r"\\\\" are not extracted.
    """
    # Test 1: Raw string with double backslash
    content1 = 'Some text\n```python\nprint(r"\\\\")\n```\nMore text'
    result1 = ContentExtractor.extract_code_blocks(content1)
    assert len(result1) == 1, f"Code block with r'\\\\' not extracted: expected 1, got {len(result1)}. Content: {repr(content1)}"

    # Test 2: Just the code block
    content2 = '```python\nprint(r"\\\\")\n```'
    result2 = ContentExtractor.extract_code_blocks(content2)
    assert len(result2) == 1, f"Code block with r'\\\\' not extracted: expected 1, got {len(result2)}"

    # Test 3: Raw string with multiple backslashes
    content3 = '```python\npath = r"C:\\\\Users\\\\test"\nprint(path)\n```'
    result3 = ContentExtractor.extract_code_blocks(content3)
    assert len(result3) == 1, f"Code block with r'C:\\\\Users\\\\test' not extracted: expected 1, got {len(result3)}"


def test_extract_code_blocks_odd_number_of_backticks():
    """Test that odd number of backticks doesn't create invalid code blocks.

    This test exposes a bug where 7+ backticks are incorrectly parsed.
    """
    # 7 backticks - should not extract or should extract empty
    content1 = '```````'
    blocks1 = ContentExtractor.extract_code_blocks(content1)
    # Currently returns ['```\n`\n```'] which is wrong
    # Either should return [] (no valid code block) or ['```\n\n```'] (empty)
    # But NOT with a backtick as content
    if blocks1:
        block = blocks1[0]
        # If it extracts, content should be empty (not a backtick)
        # Check if content between ``` and ``` is just whitespace/newlines
        lines = block.split('\n')
        if len(lines) >= 3:
            content = '\n'.join(lines[1:-1])
            assert content.strip() == '', f"Odd backticks should not extract content, got: {repr(content)}"

    # 9 backticks
    content2 = '`````````'
    blocks2 = ContentExtractor.extract_code_blocks(content2)
    if blocks2:
        block = blocks2[0]
        lines = block.split('\n')
        if len(lines) >= 3:
            content = '\n'.join(lines[1:-1])
            assert content.strip() == '', f"Odd backticks should not extract content, got: {repr(content)}"

    # 11 backticks
    content3 = '```````````'
    blocks3 = ContentExtractor.extract_code_blocks(content3)
    if blocks3:
        block = blocks3[0]
        lines = block.split('\n')
        if len(lines) >= 3:
            content = '\n'.join(lines[1:-1])
            assert content.strip() == '', f"Odd backticks should not extract content, got: {repr(content)}"


def test_extract_code_blocks_uppercase_string_prefixes():
    """Test extracting code blocks with uppercase string prefixes (R, BR, FR, etc.).

    This test exposes a bug where uppercase string prefixes are not recognized
    as raw strings, causing incorrect backslash handling.
    """
    # Test 1: Uppercase R prefix
    content1 = '''```python
data = R"Hello\\nWorld"  # Should be raw: backslash-n, not newline
print(data)
```'''
    blocks1 = ContentExtractor.extract_code_blocks(content1)
    assert len(blocks1) == 1, f"Expected 1 code block with R prefix, got {len(blocks1)}"
    # The source should preserve double backslash (\\ in source becomes \ in string)
    assert 'R"Hello\\nWorld"' in blocks1[0], f"Uppercase R string not preserved correctly: {blocks1[0]}"

    # Test 2: Uppercase BR prefix (bytes raw string)
    content2 = '''```python
data = BR"Hello\\nWorld"
print(data)
```'''
    blocks2 = ContentExtractor.extract_code_blocks(content2)
    assert len(blocks2) == 1, f"Expected 1 code block with BR prefix, got {len(blocks2)}"
    assert 'BR"Hello\\nWorld"' in blocks2[0], f"Uppercase BR string not preserved correctly: {blocks2[0]}"

    # Test 3: Mixed case prefix (Br)
    content3 = '''```python
data = Br"Hello\\nWorld"
print(data)
```'''
    blocks3 = ContentExtractor.extract_code_blocks(content3)
    assert len(blocks3) == 1, f"Expected 1 code block with Br prefix, got {len(blocks3)}"
    assert 'Br"Hello\\nWorld"' in blocks3[0], f"Mixed case Br string not preserved correctly: {blocks3[0]}"

    # Test 4: Uppercase FR prefix (formatted raw string)
    content4 = '''```python
name = "world"
msg = FR"Hello {name}\\n"  # Raw f-string: backslash-n literal
print(msg)
```'''
    blocks4 = ContentExtractor.extract_code_blocks(content4)
    assert len(blocks4) == 1, f"Expected 1 code block with FR prefix, got {len(blocks4)}"
    assert 'FR"Hello {name}\\n"' in blocks4[0], f"Uppercase FR string not preserved correctly: {blocks4[0]}"

    # Test 5: Triple-quoted uppercase raw string
    content5 = '''```python
doc = R"""Hello\\nWorld"""
print(doc)
```'''
    blocks5 = ContentExtractor.extract_code_blocks(content5)
    assert len(blocks5) == 1, f"Expected 1 code block with triple-quoted R string, got {len(blocks5)}"
    assert 'R"""Hello\\nWorld"""' in blocks5[0], f"Triple-quoted uppercase R string not preserved: {blocks5[0]}"


def test_extract_code_blocks_invalid_string_prefixes():
    """Test that invalid Python string prefixes are not recognized as raw strings.

    This test exposes a bug where invalid prefixes like 'rr', 'ur', 'ru', 'rbbr'
    are incorrectly recognized as raw string prefixes.
    """
    # Test 1: 'rr' prefix (invalid - duplicate 'r')
    content1 = '''```python
data = rr"Hello\\nWorld"  # Invalid prefix, should not be treated as raw
print(data)
```'''
    blocks1 = ContentExtractor.extract_code_blocks(content1)
    assert len(blocks1) == 1, f"Expected 1 code block with invalid rr prefix, got {len(blocks1)}"
    # The string should be preserved as-is, not treated as raw
    # In a raw string, \\n would be literal backslash-n, but rr is invalid
    # The current buggy implementation treats rr as raw
    block1 = blocks1[0]
    # Check that the code contains rr"Hello\\nWorld" (preserved as-is)
    assert 'rr"Hello\\nWorld"' in block1, f"Invalid rr prefix not preserved correctly: {block1}"

    # Test 2: 'ur' prefix (invalid in Python 3 - 'u' can't combine with 'r')
    content2 = '''```python
data = ur"Hello\\nWorld"  # Invalid prefix
print(data)
```'''
    blocks2 = ContentExtractor.extract_code_blocks(content2)
    assert len(blocks2) == 1, f"Expected 1 code block with invalid ur prefix, got {len(blocks2)}"
    assert 'ur"Hello\\nWorld"' in blocks2[0], f"Invalid ur prefix not preserved correctly: {blocks2[0]}"

    # Test 3: 'ru' prefix (invalid in Python 3 - 'r' can't combine with 'u')
    content3 = '''```python
data = ru"Hello\\nWorld"  # Invalid prefix
print(data)
```'''
    blocks3 = ContentExtractor.extract_code_blocks(content3)
    assert len(blocks3) == 1, f"Expected 1 code block with invalid ru prefix, got {len(blocks3)}"
    assert 'ru"Hello\\nWorld"' in blocks3[0], f"Invalid ru prefix not preserved correctly: {blocks3[0]}"

    # Test 4: 'rbbr' prefix (invalid - duplicate 'b' and 'r')
    content4 = '''```python
data = rbbr"Hello\\nWorld"  # Invalid prefix
print(data)
```'''
    blocks4 = ContentExtractor.extract_code_blocks(content4)
    assert len(blocks4) == 1, f"Expected 1 code block with invalid rbbr prefix, got {len(blocks4)}"
    assert 'rbbr"Hello\\nWorld"' in blocks4[0], f"Invalid rbbr prefix not preserved correctly: {blocks4[0]}"

    # Test 5: 'ff' prefix (invalid - duplicate 'f')
    content5 = '''```python
data = ff"Hello {name}"  # Invalid prefix
print(data)
```'''
    blocks5 = ContentExtractor.extract_code_blocks(content5)
    assert len(blocks5) == 1, f"Expected 1 code block with invalid ff prefix, got {len(blocks5)}"
    assert 'ff"Hello {name}"' in blocks5[0], f"Invalid ff prefix not preserved correctly: {blocks5[0]}"


def test_extract_code_blocks_apostrophe_in_string_bug():
    """Test extracting code blocks with apostrophes in strings.

    This test exposes a bug where apostrophes in words like "don't" inside strings
    cause incorrect string termination in the parser.
    """
    # Test 1: Double-quoted string with apostrophe
    content1 = '''```python
message = "I don't know what to do"
print(message)
```'''
    blocks1 = ContentExtractor.extract_code_blocks(content1)
    assert len(blocks1) == 1, f"Expected 1 code block with apostrophe in string, got {len(blocks1)}"
    # The entire string should be preserved
    block1 = blocks1[0]
    assert '"I don\'t know what to do"' in block1, f"Apostrophe in double-quoted string not preserved: {block1}"

    # Test 2: Single-quoted string with apostrophe (should fail - apostrophe ends string)
    content2 = '''```python
message = 'I don\\'t know what to do'  # Escaped apostrophe
print(message)
```'''
    blocks2 = ContentExtractor.extract_code_blocks(content2)
    assert len(blocks2) == 1, f"Expected 1 code block with escaped apostrophe, got {len(blocks2)}"
    block2 = blocks2[0]
    # The escaped apostrophe should be preserved
    assert "'I don\\'t know what to do'" in block2, f"Escaped apostrophe in single-quoted string not preserved: {block2}"

    # Test 3: Triple-quoted string with apostrophe
    content3 = '''```python
message = """I don't know what to do"""
print(message)
```'''
    blocks3 = ContentExtractor.extract_code_blocks(content3)
    assert len(blocks3) == 1, f"Expected 1 code block with apostrophe in triple-quoted string, got {len(blocks3)}"
    block3 = blocks3[0]
    assert '"""I don\'t know what to do"""' in block3, f"Apostrophe in triple-quoted string not preserved: {block3}"

    # Test 4: Multiple apostrophes in string
    content4 = '''```python
message = "It isn't right that they don't understand"
print(message)
```'''
    blocks4 = ContentExtractor.extract_code_blocks(content4)
    assert len(blocks4) == 1, f"Expected 1 code block with multiple apostrophes, got {len(blocks4)}"
    block4 = blocks4[0]
    assert '"It isn\'t right that they don\'t understand"' in block4, f"Multiple apostrophes not preserved: {block4}"


def test_extract_code_blocks_escaped_quote_bug():
    """Test extracting code blocks with escaped quotes.

    This test exposes a bug in the _process_char function's handling of
    escaped quotes in strings, particularly with raw strings and
    consecutive backslashes.
    """
    # Test 1: Regular string with escaped quote followed by apostrophe
    # This tests the backslash counting logic
    content1 = '''```python
s = "test\\"s value"  # Escaped quote followed by 's
print(s)
```'''
    blocks1 = ContentExtractor.extract_code_blocks(content1)
    assert len(blocks1) == 1, f"Expected 1 code block with escaped quote, got {len(blocks1)}"
    block1 = blocks1[0]
    # The escaped quote should be preserved
    assert '"test\\"s value"' in block1, f"Escaped quote not preserved: {block1}"

    # Test 2: Raw string with backslash-quote (should NOT escape)
    # In raw strings, \" is literal backslash-quote, not escaped quote
    # unless there's an odd number of backslashes before the quote
    content2 = '''```python
s = r"test\\\\"  # Raw string: two backslashes then quote
print(s)
```'''
    blocks2 = ContentExtractor.extract_code_blocks(content2)
    assert len(blocks2) == 1, f"Expected 1 code block with raw string and backslashes, got {len(blocks2)}. Content: {repr(content2)}"
    block2 = blocks2[0]
    # Should be r"test\\\\" (two backslashes then quote)
    # The quote ends the string (not escaped because even number of backslashes)
    # Note: In Python source, \\\\ represents two backslashes
    # In the extracted block, we should see r"test\\\\" (four backslashes in source)
    assert 'r"test\\\\"' in block2, f"Raw string with backslash-backslash-quote not preserved: {block2}"

    # Test 3: Raw string with odd number of backslashes before quote (should escape)
    content3 = '''```python
s = r"test\\\\\\"  # Raw string: three backslashes then quote
print(s)
```'''
    blocks3 = ContentExtractor.extract_code_blocks(content3)
    assert len(blocks3) == 1, f"Expected 1 code block with raw string and odd backslashes, got {len(blocks3)}"
    block3 = blocks3[0]
    # Should be r"test\\\\\\" (three backslashes then quote)
    # The quote is escaped (odd number of backslashes)
    # In source: \\\\\\\ represents three backslashes
    assert 'r"test\\\\\\"' in block3, f"Raw string with odd backslashes before quote not preserved: {block3}"

    # Test 4: Complex case with multiple escaped quotes
    content4 = '''```python
s = "He said \\"hello\\", she said \\"goodbye\\""
print(s)
```'''
    blocks4 = ContentExtractor.extract_code_blocks(content4)
    assert len(blocks4) == 1, f"Expected 1 code block with multiple escaped quotes, got {len(blocks4)}"
    block4 = blocks4[0]
    assert '"He said \\"hello\\", she said \\"goodbye\\""' in block4, f"Multiple escaped quotes not preserved: {block4}"

    # Test 5: Edge case: backslash at end of file/block (should not crash)
    content5 = '''```python
s = "test\\"
```'''
    blocks5 = ContentExtractor.extract_code_blocks(content5)
    # This might or might not extract a block depending on implementation
    # But it shouldn't crash
    if blocks5:
        blocks5[0]
        # Should contain the string (possibly malformed)


def test_extract_code_blocks_apostrophe_string_delimiter():
    """Test that apostrophes in single-quoted strings are treated as string delimiters.

    In Python, 'don't' is a syntax error (should be 'don\'t').
    The parser should treat the apostrophe as a string delimiter, not as part of the word.
    """
    # Test 1: Single-quoted string with apostrophe (invalid Python)
    # The parser should extract the code block correctly
    content1 = '''```python
s = 'don't panic'  # Invalid Python: apostrophe ends string
```'''
    blocks1 = ContentExtractor.extract_code_blocks(content1)
    assert len(blocks1) == 1, f"Expected 1 code block, got {len(blocks1)}"
    block1 = blocks1[0]
    # Should contain the code as-is
    assert "'don't panic'" in block1, f"Code with apostrophe not preserved: {block1}"

    # Test 2: Escaped apostrophe in single-quoted string (valid Python)
    content2 = '''```python
s = 'don\\'t panic'  # Valid: escaped apostrophe
```'''
    blocks2 = ContentExtractor.extract_code_blocks(content2)
    assert len(blocks2) == 1, f"Expected 1 code block with escaped apostrophe, got {len(blocks2)}"
    block2 = blocks2[0]
    # Should contain escaped apostrophe
    assert "don\\'t" in block2 or "don\'t" in block2, f"Escaped apostrophe not preserved: {block2}"

    # Test 3: Double-quoted string with apostrophe (valid Python)
    content3 = '''```python
s = "don't panic"  # Valid: apostrophe in double-quoted string
```'''
    blocks3 = ContentExtractor.extract_code_blocks(content3)
    assert len(blocks3) == 1, f"Expected 1 code block with apostrophe in double quotes, got {len(blocks3)}"
    block3 = blocks3[0]
    # Should contain apostrophe
    assert '"don\'t panic"' in block3 or '"don\'t panic"' in block3, f"Apostrophe in double-quoted string not preserved: {block3}"

    # Test 4: Comment with apostrophe
    content4 = '''```python
# This isn't a string
s = "hello"
```'''
    blocks4 = ContentExtractor.extract_code_blocks(content4)
    assert len(blocks4) == 1, f"Expected 1 code block with comment, got {len(blocks4)}"
    block4 = blocks4[0]
    # Should contain comment with apostrophe
    assert "isn't" in block4, f"Comment with apostrophe not preserved: {block4}"


def test_extract_code_blocks_line_continuation_bug():
    """Test extracting code blocks with line continuation in strings.

    This test exposes a bug where strings with line continuation (backslash-newline)
    are incorrectly terminated at the newline, causing backticks inside the continued
    string to be misinterpreted as code block markers.
    """
    # Test 1: String with line continuation containing backticks
    content1 = '''```python
code = "hello\\
`world`"
print(code)
```'''
    blocks1 = ContentExtractor.extract_code_blocks(content1)
    assert len(blocks1) == 1, f"Expected 1 code block with line continuation, got {len(blocks1)}"
    block1 = blocks1[0]
    # The entire string should be preserved, including backticks
    # The string is "hello`world`" (line continuation joins them)
    assert '"hello\\' in block1, f"Line continuation backslash not preserved: {block1}"
    assert '`world`"' in block1, f"Backticks in continued string not preserved: {block1}"

    # Test 2: Multiple line continuations
    content2 = '''```python
text = "first\\
second\\
third"
print(text)
```'''
    blocks2 = ContentExtractor.extract_code_blocks(content2)
    assert len(blocks2) == 1, f"Expected 1 code block with multiple line continuations, got {len(blocks2)}"

    # Test 3: Line continuation in raw string (should still work)
    content3 = '''```python
text = r"raw\\
string"
print(text)
```'''
    blocks3 = ContentExtractor.extract_code_blocks(content3)
    assert len(blocks3) == 1, f"Expected 1 code block with line continuation in raw string, got {len(blocks3)}"

    # Test 4: Line continuation with escaped newline (\\n vs \\\n)
    content4 = '''```python
# \\n is newline character, \\\n is line continuation
text = "line1\\nline2\\\nline3"
print(repr(text))
```'''
    blocks4 = ContentExtractor.extract_code_blocks(content4)
    assert len(blocks4) == 1, f"Expected 1 code block with mixed newlines, got {len(blocks4)}"

    # Test 5: Critical test - backticks after line continuation
    # If parser incorrectly ends string at newline, it will see `backtick` as code block
    content5 = '''Some text before
```python
s = "string with\\
`backtick` inside"
print(s)
```
Some text after'''
    blocks5 = ContentExtractor.extract_code_blocks(content5)
    # Should extract exactly one code block
    assert len(blocks5) == 1, f"Expected 1 code block, got {len(blocks5)}. Parser may have incorrectly interpreted backtick as code block marker."
    block5 = blocks5[0]
    # Should contain the full string with backticks
    assert '`backtick`' in block5, f"Backticks after line continuation not preserved: {block5}"


def test_extract_code_blocks_line_continuation_escaped_newline_bug():
    """Test that line continuation and escaped newlines don't terminate strings.

    This test exposes a bug where the parser ends strings at newlines
    even when the newline is escaped (was_escaped = True).
    """
    # Test 1: Line continuation with backslash-newline
    # The bug: parser ends string at newline even though was_escaped = True
    content1 = '''```python
s = "hello\\
world"  # Line continuation
print(s)
```'''
    blocks1 = ContentExtractor.extract_code_blocks(content1)
    assert len(blocks1) == 1, f"Line continuation: expected 1 block, got {len(blocks1)}"

    # Test 2: More critical - backticks after line continuation
    # If parser incorrectly ends string at newline, backticks won't be in string
    content2 = '''Some text
```python
s = "start\\
```middle\\
end"
print(s)
```
More text'''
    blocks2 = ContentExtractor.extract_code_blocks(content2)
    # Should extract 1 code block (lines 2-6)
    # If bug exists: parser ends string at first newline, sees ``` as code block end
    # Would extract lines 2-4 only (or wrong number of blocks)
    assert len(blocks2) == 1, f"Line continuation with backticks: expected 1 block, got {len(blocks2)}. Parser may have incorrectly ended string at newline."

    block2 = blocks2[0]
    # Should contain the full string with backticks
    assert '```middle' in block2, f"Backticks after line continuation not in string: {block2}"

    # Test 3: Escaped newline character \n (backslash-n)
    content3 = '''```python
s = "hello\\nworld"  # Escaped newline character
print(s)
```'''
    blocks3 = ContentExtractor.extract_code_blocks(content3)
    assert len(blocks3) == 1, f"Escaped newline: expected 1 block, got {len(blocks3)}"

    # Test 4: Raw string with backslash-newline (line continuation still works)
    content4 = '''```python
s = r"hello\\
world"  # Raw string with line continuation
print(s)
```'''
    blocks4 = ContentExtractor.extract_code_blocks(content4)
    assert len(blocks4) == 1, f"Raw string line continuation: expected 1 block, got {len(blocks4)}"


def test_string_prefix_validation_empty_string_bug():
    """Test that empty string is not considered a valid Python string prefix.

    This test exposes a bug where _is_valid_string_prefix returns True for
    an empty string, which is incorrect. An empty string is not a valid
    Python string prefix.
    """
    from henchman.utils.intelligent_context_parser import _ParserState

    state = _ParserState()

    # Empty string should NOT be a valid string prefix
    assert not state._is_valid_string_prefix(""), "Empty string should not be a valid string prefix"

    # Also test _is_valid_raw_string_prefix for consistency
    assert not state._is_valid_raw_string_prefix(""), "Empty string should not be a valid raw string prefix"

    # Test some valid prefixes to ensure we're not breaking anything
    assert state._is_valid_string_prefix("r"), "Single 'r' should be a valid string prefix"
    assert state._is_valid_string_prefix("b"), "Single 'b' should be a valid string prefix"
    assert state._is_valid_string_prefix("f"), "Single 'f' should be a valid string prefix"
    assert state._is_valid_string_prefix("u"), "Single 'u' should be a valid string prefix"
    assert state._is_valid_string_prefix("br"), "'br' should be a valid string prefix"
    assert state._is_valid_string_prefix("fr"), "'fr' should be a valid string prefix"


def test_extract_code_blocks_none_value_bug():
    """Test that extract_code_blocks never returns None values in the list.

    This test exposes a bug where malformed code blocks cause _extract_single_block
    to return None, which is then appended to the result list, violating the
    method's contract of returning a list of strings.
    """
    # Test 1: Malformed code block with no closing backticks
    # This should return an empty list, not a list containing None
    content1 = '```python\nprint("hello")\n'
    result1 = ContentExtractor.extract_code_blocks(content1)
    # Should return empty list, not [None]
    assert isinstance(result1, list), f"Result should be a list, got {type(result1)}"
    assert all(isinstance(item, str) for item in result1), f"All items should be strings, got {result1}"

    # Test 2: Mixed content with valid and malformed code blocks
    content2 = '''Some text
```python
print("valid")
```
More text
```python
print("malformed")
'''
    result2 = ContentExtractor.extract_code_blocks(content2)
    # Should return list with only the valid code block
    assert isinstance(result2, list), f"Result should be a list, got {type(result2)}"
    assert all(isinstance(item, str) for item in result2), f"All items should be strings, got {result2}"
    assert len(result2) == 1, f"Should have 1 valid code block, got {len(result2)}"
    assert 'print("valid")' in result2[0]

    # Test 3: Ensure we can safely iterate over result
    content3 = '```python\nprint("test")\n```'
    result3 = ContentExtractor.extract_code_blocks(content3)
    # This should not raise TypeError
    for block in result3:
        assert isinstance(block, str), f"Block should be string, got {type(block)}"
        assert len(block) > 0, "Block should not be empty"

    # Test 4: Empty or whitespace-only code blocks should still be strings
    content4 = '```\n```'
    result4 = ContentExtractor.extract_code_blocks(content4)
    assert isinstance(result4, list), f"Result should be a list, got {type(result4)}"
    assert all(isinstance(item, str) for item in result4), f"All items should be strings, got {result4}"
    if result4:  # Some implementations might return empty list for empty blocks
        assert result4[0] == '```\n\n```' or '```' in result4[0]


def test_extract_code_blocks_two_backticks_bug():
    """Test that two backticks don't cause infinite loop or incorrect parsing.

    This test exposes a bug where two backticks (``) could cause the parser
    to get stuck or incorrectly advance the position.
    """
    # Test 1: Two backticks in content
    content1 = '``two backticks``'
    result1 = ContentExtractor.extract_code_blocks(content1)
    # Should return empty list (not a valid code block)
    assert result1 == [], f"Two backticks should not be extracted as code block: {result1}"

    # Test 2: Two backticks followed by valid code block
    content2 = '``not a block``\n```python\nprint("hello")\n```'
    result2 = ContentExtractor.extract_code_blocks(content2)
    # Should extract only the valid code block
    assert len(result2) == 1, f"Should extract 1 code block, got {len(result2)}"
    assert 'print("hello")' in result2[0]

    # Test 3: Two backticks at end of line
    content3 = 'Some text `` more text'
    result3 = ContentExtractor.extract_code_blocks(content3)
    assert result3 == [], f"Two backticks in text should not be extracted: {result3}"

    # Test 4: Edge case - two backticks then three backticks
    content4 = '`````python\nprint("test")\n`````'
    result4 = ContentExtractor.extract_code_blocks(content4)
    # This is actually 5 backticks, which should be a valid code block
    # The parser should handle this correctly
    if result4:
        # If it extracts, should contain the code
        assert 'print("test")' in result4[0]


def test_extract_code_blocks_language_with_hyphen_bug():
    """Test that language specifiers with hyphens are correctly parsed.

    This test exposes a bug where language specifiers like 'python-test'
    or 'jsx-static' are not recognized because the parser requires
    whitespace after the language, but in empty code blocks or code blocks
    without newline after language, the next character is a backtick.
    """
    # Test 1: Language with hyphen, empty code block
    content1 = '```python-test\n```'
    result1 = ContentExtractor.extract_code_blocks(content1)
    # Should extract code block with language 'python-test'
    assert len(result1) == 1, f"Language with hyphen not extracted: expected 1, got {len(result1)}"
    block1 = result1[0]
    # Should contain 'python-test' in the language part
    assert 'python-test' in block1, f"Language 'python-test' not preserved: {block1}"

    # Test 2: Language with hyphen, with code
    content2 = '```python-test\nprint("test")\n```'
    result2 = ContentExtractor.extract_code_blocks(content2)
    assert len(result2) == 1, f"Language with hyphen and code not extracted: expected 1, got {len(result2)}"
    block2 = result2[0]
    assert 'python-test' in block2, f"Language 'python-test' not preserved in code block: {block2}"
    assert 'print("test")' in block2

    # Test 3: Language with multiple hyphens
    content3 = '```python-3-11-test\nprint("test")\n```'
    result3 = ContentExtractor.extract_code_blocks(content3)
    assert len(result3) == 1, f"Language with multiple hyphens not extracted: expected 1, got {len(result3)}"
    block3 = result3[0]
    assert 'python-3-11-test' in block3, f"Language 'python-3-11-test' not preserved: {block3}"

    # Test 4: Language with underscore (also allowed)
    content4 = '```python_test\nprint("test")\n```'
    result4 = ContentExtractor.extract_code_blocks(content4)
    assert len(result4) == 1, f"Language with underscore not extracted: expected 1, got {len(result4)}"
    block4 = result4[0]
    assert 'python_test' in block4, f"Language 'python_test' not preserved: {block4}"

    # Test 5: Language with dot (e.g., 'python.json' for JSON in Python code block)
    content5 = '```python.json\n{"test": "value"}\n```'
    result5 = ContentExtractor.extract_code_blocks(content5)
    assert len(result5) == 1, f"Language with dot not extracted: expected 1, got {len(result5)}"
    block5 = result5[0]
    assert 'python.json' in block5, f"Language 'python.json' not preserved: {block5}"


def test_extract_code_blocks_language_no_whitespace_bug():
    """Test that language specifiers without whitespace before closing fence are parsed.

    This test exposes a bug where language specifiers followed immediately by
    closing backticks (e.g., '```python```') are not recognized because the
    parser requires whitespace after the language, but in empty code blocks,
    the language is immediately followed by the closing fence.

    THIS TEST SHOULD FAIL WITH THE CURRENT IMPLEMENTATION.
    """
    # Test 1: Empty code block with language, no whitespace after language
    # This is '```python```' - valid empty code block
    # The parser should extract it with language 'python'
    content1 = '```python```'
    result1 = ContentExtractor.extract_code_blocks(content1)
    # THIS SHOULD BE 1 BUT IS PROBABLY 0
    assert len(result1) == 1, f"Empty code block '```python```' not extracted: expected 1, got {len(result1)}. This exposes the bug!"
    if result1:
        block1 = result1[0]
        assert 'python' in block1, f"Language 'python' not preserved: {block1}"

    # Test 2: Same but with language that has hyphen
    content2 = '```python-test```'
    result2 = ContentExtractor.extract_code_blocks(content2)
    assert len(result2) == 1, f"Empty code block '```python-test```' not extracted: expected 1, got {len(result2)}"
    if result2:
        block2 = result2[0]
        assert 'python-test' in block2, f"Language 'python-test' not preserved: {block2}"

    # Test 3: Language with newline (valid, should work)
    content3 = '```python\n```'
    result3 = ContentExtractor.extract_code_blocks(content3)
    assert len(result3) == 1, f"Empty code block with newline not extracted: expected 1, got {len(result3)}"
    block3 = result3[0]
    assert 'python' in block3, f"Language 'python' not preserved: {block3}"

    # Test 4: Language with space (valid, should work)
    content4 = '```python ```'
    result4 = ContentExtractor.extract_code_blocks(content4)
    assert len(result4) == 1, f"Empty code block with space not extracted: expected 1, got {len(result4)}"
    if result4:
        block4 = result4[0]
        assert 'python' in block4, f"Language 'python' not preserved: {block4}"

    # Test 5: Non-empty code block without whitespace after language
    # This is '```pythonprint("hello")```' - malformed (no whitespace after language)
    # With the fix, it might be extracted as language='pythonprint', code='("hello")'
    # OR might not be extracted at all
    content5 = '```pythonprint("hello")```'
    result5 = ContentExtractor.extract_code_blocks(content5)
    # Accept either behavior:
    # 1. Not extracted (empty list) - strict parsing
    # 2. Extracted with language='pythonprint' - lenient parsing (current behavior after fix)
    # 3. Extracted without language (language='') - alternative lenient parsing
    if result5:
        block5 = result5[0]
        # If extracted, should contain the code (maybe with language)
        # The code might be '("hello")' or 'print("hello")' depending on parsing
        assert '("hello")' in block5 or 'print("hello")' in block5


def test_is_apostrophe_in_word_negative_index_bug():
    """Test that _is_apostrophe_in_word handles negative indices correctly.

    This test exposes a bug where the function raises IndexError when
    i is a negative index and i-1 is out of bounds.
    """
    from henchman.utils.intelligent_context_parser import _ApostropheDetector, _ParserState

    state = _ParserState()

    # Test 1: Single quote character, i = -1 (last character)
    # This should not raise IndexError
    text1 = "'"
    try:
        result1 = _ApostropheDetector.is_apostrophe_in_word(state, text1, -1)
        # Should return False (not an apostrophe in a word)
        assert result1 is False, f"Expected False for single quote, got {result1}"
    except IndexError as e:
        pytest.fail(f"IndexError raised for text='{text1}', i=-1: {e}")

    # Test 2: String "a'", i = -1 (points to the quote)
    text2 = "a'"
    try:
        result2 = _ApostropheDetector.is_apostrophe_in_word(state, text2, -1)
        # 'a' is alnum, next char is end of string, so should return False
        assert result2 is False, f"Expected False for 'a\\'', i=-1, got {result2}"
    except IndexError as e:
        pytest.fail(f"IndexError raised for text='{text2}', i=-1: {e}")

    # Test 3: String "don't", i = 3 (the apostrophe)
    text3 = "don't"
    try:
        result3 = _ApostropheDetector.is_apostrophe_in_word(state, text3, 3)
        # Should return True (apostrophe in word)
        assert result3 is True, f"Expected True for 'don\\'t', i=3, got {result3}"
    except IndexError as e:
        pytest.fail(f"IndexError raised for text='{text3}', i=3: {e}")

    # Test 4: String "ur'", i = -1 (last character, the quote)
    # Tests string prefix detection with negative index
    text4 = "ur'"
    try:
        result4 = _ApostropheDetector.is_apostrophe_in_word(state, text4, -1)
        # "ur" is invalid string prefix, should return False
        assert result4 is False, f"Expected False for 'ur\\'', i=-1, got {result4}"
    except IndexError as e:
        pytest.fail(f"IndexError raised for text='{text4}', i=-1: {e}")

    # Test 5: Edge case - i = -len(text) (first character as negative index)
    text5 = "'test"
    try:
        result5 = _ApostropheDetector.is_apostrophe_in_word(state, text5, -5)  # -len(text) = -5
        # i = -5, i-1 = -6 which is out of bounds
        # The function should handle this without IndexError
        # Should return False (quote at beginning, not apostrophe in word)
        assert result5 is False, f"Expected False for '\\'test', i=-5, got {result5}"
    except IndexError as e:
        pytest.fail(f"IndexError raised for text='{text5}', i=-5: {e}")
