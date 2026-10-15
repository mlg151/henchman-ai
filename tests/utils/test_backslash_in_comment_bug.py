"""Test backslash in comment bug."""

from henchman.utils.intelligent_context import ContentExtractor


def test_backslash_in_comment():
    """Test code block with backslash in comment."""
    content = '''```python
# This is a comment with backslash \\
print("hello")
```'''
    result = ContentExtractor.extract_code_blocks(content)
    print(f"Result: {result[0] if result else 'No result'}")
    assert len(result) == 1, f"Expected 1 code block, got {len(result)}"
    # Should preserve the comment with backslash
    assert '# This is a comment with backslash \\' in result[0], f"Comment with backslash not preserved: {result[0]}"


def test_backslash_at_end_of_line():
    """Test line continuation backslash."""
    content = '''```python
s = "hello" \\
    + "world"
```'''
    result = ContentExtractor.extract_code_blocks(content)
    print(f"Result: {result[0] if result else 'No result'}")
    assert len(result) == 1, f"Expected 1 code block, got {len(result)}"
    # Line continuation should be preserved
    assert 's = "hello" \\' in result[0], f"Line continuation not preserved: {result[0]}"


if __name__ == "__main__":
    test_backslash_in_comment()
    test_backslash_at_end_of_line()
    print("All tests passed")
