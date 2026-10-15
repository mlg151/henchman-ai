"""Tests for ContentExtractor class."""

from henchman.utils.intelligent_context import ContentExtractor


class TestContentExtractor:
    """Test ContentExtractor functionality."""

    def test_extract_code_blocks_empty(self) -> None:
        """Test extracting code blocks from empty content."""
        result = ContentExtractor.extract_code_blocks("")
        assert result == []

    def test_extract_code_blocks_none_content(self) -> None:
        """Test extracting code blocks from None content."""
        result = ContentExtractor.extract_code_blocks(None)  # type: ignore[arg-type]
        assert result == []

    def test_extract_code_blocks_single_block(self) -> None:
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
        assert "return \"world\"" in result[0]

    def test_extract_code_blocks_multiple_blocks(self) -> None:
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
        assert "print(\"hello\")" in result[0]
        assert "ls -la" in result[1]

    def test_extract_code_blocks_no_blocks(self) -> None:
        """Test extracting code blocks when none exist."""
        content = "Just regular text without code blocks"
        result = ContentExtractor.extract_code_blocks(content)
        assert result == []

    def test_extract_sections_with_error_patterns(self) -> None:
        """Test extracting error sections."""
        content = """Everything is fine
Error: Something went wrong
Traceback (most recent call last):
  File "test.py", line 1, in <module>
    raise ValueError("test")
ValueError: test
Everything is still fine"""
        result = ContentExtractor.extract_error_sections(content)
        assert len(result) >= 2  # Should find both error and traceback
        assert any("Error: Something went wrong" in s for s in result)
        assert any("Traceback" in s for s in result)

    def test_extract_sections_with_tool_patterns(self) -> None:
        """Test extracting tool sections."""
        content = """Starting execution
Tool call: read_file
Calling tool: write_file
Executing: shell command
Function: some_function
Done"""
        result = ContentExtractor.extract_tool_sections(content)
        assert len(result) >= 4  # Should find all tool-related lines
        assert any("Tool call: read_file" in s for s in result)
        assert any("Calling tool: write_file" in s for s in result)

    def test_extract_code_blocks_with_apostrophe_bug(self) -> None:
        """Test for bug where apostrophe in word breaks code block extraction.

        This test demonstrates a bug where an apostrophe in a word (like "isn't")
        is incorrectly treated as a string delimiter, causing the function to
        enter string mode and never exit, preventing recognition of closing backticks.
        """
        content = '''```python
# Line with apostrophe in word
`this looks like closing but isn't`
print("done")
```'''
        result = ContentExtractor.extract_code_blocks(content)
        # This should extract one code block but currently fails (returns 0)
        assert len(result) == 1, f"Expected 1 code block, got {len(result)}"
        assert '`this looks like closing but isn\'t`' in result[0]
        assert 'print("done")' in result[0]

    def test_extract_code_blocks_with_various_apostrophes(self) -> None:
        """Test code block extraction with various apostrophe scenarios."""
        # Test 1: Multiple apostrophes
        content1 = '''```python
print("It's a test")
print('Isn\'t this working?')
print("Won't fail")
```'''
        result1 = ContentExtractor.extract_code_blocks(content1)
        assert len(result1) == 1
        assert "It's a test" in result1[0]
        assert "Isn't this working?" in result1[0]
        assert "Won't fail" in result1[0]

        # Test 2: Apostrophe at end of line
        content2 = '''```python
message = "That's all folks'"
print(message)
```'''
        result2 = ContentExtractor.extract_code_blocks(content2)
        assert len(result2) == 1
        assert "That's all folks'" in result2[0]

        # Test 3: Mixed quotes and apostrophes
        content3 = '''```python
s1 = "It's a 'test' string"
s2 = 'This is a "test" string'
```'''
        result3 = ContentExtractor.extract_code_blocks(content3)
        assert len(result3) == 1
        assert "It's a 'test' string" in result3[0]
        assert 'This is a "test" string' in result3[0]

    def test_extract_keyword_sections_with_default_keywords(self) -> None:
        """Test extracting sections with default keywords."""
        content = """This is a normal section.
IMPORTANT: This is critical.
TODO: Need to fix this.
FIXME: Another thing to fix."""
        result = ContentExtractor.extract_keyword_sections(content)
        # Should find sections containing keywords
        assert len(result) > 0
        # Check that we found at least one section with IMPORTANT
        assert any("IMPORTANT" in section for section in result)

    def test_extract_keyword_sections_with_custom_keywords(self) -> None:
        """Test extracting sections with custom keywords."""
        content = """Line 1
CRITICAL: Something important
Line 3
URGENT: Needs attention"""
        result = ContentExtractor.extract_keyword_sections(content, ["critical", "urgent"])
        assert len(result) == 2
        assert any("CRITICAL: Something important" in s for s in result)
        assert any("URGENT: Needs attention" in s for s in result)

    def test_extract_critical_sections(self) -> None:
        """Test extracting critical sections (integration test)."""
        content = """Normal text
```python
code block
```
Error: something wrong
TODO: fix this
Tool call: some_tool"""
        result = ContentExtractor.extract_critical_sections(content)
        # Should extract code blocks, errors, and tool calls
        # TODO is not in default keywords, so it won't be extracted separately
        assert len(result) == 3
    def test_extract_by_patterns_edge_cases(self) -> None:
        """Test edge cases for _extract_by_patterns method."""
        # Test with empty content
        result = ContentExtractor._extract_by_patterns("", ["pattern"])
        assert result == []

        # Test with empty patterns list
        result = ContentExtractor._extract_by_patterns("content", [])
        assert result == []

        # Test with None content (should handle gracefully)
        result = ContentExtractor._extract_by_patterns(None, ["pattern"])  # type: ignore[arg-type]
        assert result == []

    def test_get_context_around_line_edge_cases(self) -> None:
        """Test edge cases for _get_context_around_line method."""
        lines = ["line1", "line2", "line3", "line4", "line5"]

        # Test first line
        result = ContentExtractor._get_context_around_line(lines, 0)
        assert result is not None
        assert "line1" in result
        assert "line2" in result

        # Test last line
        result = ContentExtractor._get_context_around_line(lines, 4)
        assert result is not None
        assert "line4" in result
        assert "line5" in result

        # Test out of bounds (should handle gracefully)
        result = ContentExtractor._get_context_around_line(lines, 10)
        # Should return context for the last valid line or None
        # The implementation returns None for empty context

        # Test negative index
        result = ContentExtractor._get_context_around_line(lines, -1)
        # Should handle gracefully

    def test_line_contains_keyword_case_insensitive(self) -> None:
        """Test that keyword matching is case-insensitive."""
        line = "This is an IMPORTANT message"

        # Method should be accessible (it's a static method)
        # We'll test through extract_keyword_sections which uses it
        result = ContentExtractor.extract_keyword_sections(line, ["important"])
        assert len(result) > 0
        assert "IMPORTANT" in result[0]

    def test_code_block_with_raw_string_and_backtick(self) -> None:
        """Test code block containing raw string with backtick.

        r"`hello`" is raw string containing backticks.
        Should not be confused with code block delimiters.
        """
        content = '''```python
s = r"`hello`"
print(s)
```'''
        blocks = ContentExtractor.extract_code_blocks(content)
        assert len(blocks) == 1
        assert 'r"`hello`"' in blocks[0]

    def test_nested_code_blocks_in_string(self) -> None:
        """Test code with ``` inside string literal.

        print("```") should not end code block.
        """
        content = '''```python
print("```")
print("done")
```'''
        blocks = ContentExtractor.extract_code_blocks(content)
        assert len(blocks) == 1
        assert 'print("```")' in blocks[0]

    def test_malformed_raw_string(self) -> None:
        """Test malformed raw string r"\\" (actually valid).

        Actually r"\\" is valid (two backslashes).
        """
        content = '''```python
s = r"\\\\"
```'''
        blocks = ContentExtractor.extract_code_blocks(content)
        assert len(blocks) == 1
        # Check it doesn't crash

    def test_escape_sequence_outside_string(self) -> None:
        """Test escape sequence outside string.

        \\n in comment is just backslash-n, not newline.
        """
        content = '''```python
# This is a comment with \\n
print("hello")
```'''
        blocks = ContentExtractor.extract_code_blocks(content)
        assert len(blocks) == 1
        assert '\\n' in blocks[0]  # Should preserve backslash-n

    def test_comprehensive_string_parsing(self) -> None:
        """Comprehensive test for string parsing edge cases."""
        # Test mixed quotes and escapes
        content = '''```python
s1 = 'It\\'s a test'
s2 = "He said \\"hello\\""
s3 = r"Raw \\\\ string with `backtick`"
```'''
        blocks = ContentExtractor.extract_code_blocks(content)
        assert len(blocks) == 1

        # Test backtick in raw string
        content2 = '''```python
path = r"`/tmp/test`"
print(path)
```'''
        blocks2 = ContentExtractor.extract_code_blocks(content2)
        assert len(blocks2) == 1
        assert 'r"`/tmp/test`"' in blocks2[0]

        # Test escape sequences in strings
        content3 = '''```python
s = "Line 1\\nLine 2\\tTab"
print(s)
```'''
        blocks3 = ContentExtractor.extract_code_blocks(content3)
        assert len(blocks3) == 1

        # Test multiple code blocks with complex strings
        content4 = '''First:
```python
print("```")
```

Second:
```python
print('\\'quoted\\'')
```'''
        blocks4 = ContentExtractor.extract_code_blocks(content4)
        assert len(blocks4) == 2
