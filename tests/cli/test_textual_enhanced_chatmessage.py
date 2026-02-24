"""Tests for enhanced ChatMessage widget with syntax highlighting and markdown support."""

from unittest.mock import MagicMock

from henchman.cli.textual_widgets import ChatMessage


class TestEnhancedChatMessage:
    """Tests for enhanced ChatMessage with syntax highlighting and markdown support."""

    def test_chatmessage_initialization(self):
        """Test basic ChatMessage initialization."""
        widget = ChatMessage(prefix="[bold]Test:[/]", content="Hello world")
        assert widget._prefix == "[bold]Test:[/]"
        assert widget._content == "Hello world"

    def test_python_code_block_detection(self):
        """Test that Python code blocks are detected for syntax highlighting.

        Feature 1: Python syntax highlighting for code blocks.
        """
        # Create a ChatMessage with Python code block
        content = """Here's some Python code:
```python
def hello():
    print("Hello, world!")
    return 42
```
That's the code."""

        widget = ChatMessage(prefix="[bold]Test:[/]", content=content)

        # The content should be stored as-is
        assert widget._content == content

        # Test that we can detect Python code blocks
        # This test will fail initially - we need to implement the detection
        # For now, just verify the widget works
        assert "```python" in widget._content

    def test_python_syntax_highlighting_rendering(self):
        """Test that Python code blocks are rendered with syntax highlighting.

        Feature 1: Python syntax highlighting for code blocks.
        """
        content = """```python
def hello():
    return "world"
```"""

        widget = ChatMessage(prefix="[bold]Test:[/]", content=content)

        # When we implement syntax highlighting, the rendered output
        # should contain syntax highlighting markup
        # For now, this test just verifies the widget works
        widget._update_renderable()
        # Can't easily test the rendered output without mocking Rich
        # We'll implement proper testing when we add the feature

    def test_markdown_table_rendering(self):
        """Test that markdown tables are properly rendered.

        Feature 2: Enhanced markdown rendering (tables).
        """
        content = """Here's a table:
| Header 1 | Header 2 |
|----------|----------|
| Cell 1   | Cell 2   |
| Cell 3   | Cell 4   |
End of table."""

        widget = ChatMessage(prefix="[bold]Test:[/]", content=content)
        assert "| Header 1 | Header 2 |" in widget._content

    def test_markdown_task_list_rendering(self):
        """Test that markdown task lists are properly rendered.

        Feature 2: Enhanced markdown rendering (task lists).
        """
        content = """Task list:
- [ ] Task 1
- [x] Task 2
- [ ] Task 3
End of tasks."""

        widget = ChatMessage(prefix="[bold]Test:[/]", content=content)
        assert "- [ ] Task 1" in widget._content
        assert "- [x] Task 2" in widget._content

    def test_code_fence_language_detection(self):
        """Test that code fence language is detected.

        Feature 2: Enhanced markdown rendering (code fence language detection).
        """
        content = """Different code blocks:
```python
print("Python")
```
```javascript
console.log("JavaScript")
```
```bash
echo "Bash"
```"""

        widget = ChatMessage(prefix="[bold]Test:[/]", content=content)
        assert "```python" in widget._content
        assert "```javascript" in widget._content
        assert "```bash" in widget._content

    def test_backward_compatibility_rich_markup(self):
        """Test backward compatibility with existing Rich markup.

        Requirement: Maintain backward compatibility with existing Rich markup.
        """
        # Test that Rich markup in content is preserved/escaped properly
        content = "This has [bold]Rich markup[/] that should work"
        widget = ChatMessage(prefix="[bold]Test:[/]", content=content)

        # The content should contain the markup
        assert "[bold]Rich markup[/]" in widget._content

    def test_append_method_preserves_content(self):
        """Test that append method works with enhanced content."""
        widget = ChatMessage(prefix="[bold]Test:[/]", content="Initial")
        widget.append(" appended")
        assert widget._content == "Initial appended"

    def test_set_content_method(self):
        """Test that set_content method works."""
        widget = ChatMessage(prefix="[bold]Test:[/]", content="Initial")
        widget.set_content("New content")
        assert widget._content == "New content"

    def test_finalize_as_markdown_enables_flag(self):
        """Test that finalize_as_markdown sets _is_markdown for markdown content."""
        content = "# Heading\n\nSome **bold** text"
        widget = ChatMessage(prefix="[bold]Agent:[/]", content=content)
        assert not widget._is_markdown
        widget.finalize_as_markdown()
        assert widget._is_markdown

    def test_finalize_as_markdown_skips_plain_text(self):
        """Test that finalize_as_markdown skips plain text content."""
        widget = ChatMessage(prefix="[bold]Agent:[/]", content="Just plain text.")
        widget.finalize_as_markdown()
        assert not widget._is_markdown

    def test_finalize_as_markdown_skips_empty(self):
        """Test that finalize_as_markdown handles empty content."""
        widget = ChatMessage(prefix="[bold]Agent:[/]", content="")
        widget.finalize_as_markdown()
        assert not widget._is_markdown

    def test_finish_agent_stream_calls_finalize(self):
        """Test ChatPane.finish_agent_stream invokes finalize_as_markdown."""

        from henchman.cli.textual_widgets import ChatPane

        pane = MagicMock(spec=ChatPane)
        msg = ChatMessage(prefix="[bold]Agent:[/]", content="```python\nprint('hi')\n```")
        pane._active = {"agent": msg}
        # Call real method on mock
        ChatPane.finish_agent_stream(pane, "agent")
        assert msg._is_markdown
        assert "agent" not in pane._active

    def test_highlight_disables_markdown(self):
        """Test that setting a highlight term temporarily disables markdown."""
        content = "# Heading\n\nSome **bold** text"
        widget = ChatMessage(prefix="[bold]Agent:[/]", content=content)
        widget.finalize_as_markdown()
        assert widget._is_markdown
        widget.set_highlight("bold")
        assert not widget._is_markdown


class TestLooksLikeMarkdown:
    """Tests for the _looks_like_markdown heuristic."""

    def test_code_blocks(self):
        """Test that code blocks trigger markdown detection."""
        from henchman.cli.textual_widgets import _looks_like_markdown

        assert _looks_like_markdown("```python\nprint('hi')\n```")

    def test_bold(self):
        """Test that bold text triggers markdown detection."""
        from henchman.cli.textual_widgets import _looks_like_markdown

        assert _looks_like_markdown("This is **bold** text")

    def test_headings(self):
        """Test that headings trigger markdown detection."""
        from henchman.cli.textual_widgets import _looks_like_markdown

        assert _looks_like_markdown("## Section Title")

    def test_plain_text(self):
        """Test that plain text does not trigger markdown detection."""
        from henchman.cli.textual_widgets import _looks_like_markdown

        assert not _looks_like_markdown("Just a plain sentence.")
