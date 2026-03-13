"""Test file for intelligent_context.py refactoring."""

import pytest
from henchman.providers.base import Message
from henchman.utils.intelligent_context import (
    IntelligentContextManager,
    IntelligentContextConfig,
    ContentExtractor,
)


def test_content_extractor_error_sections():
    """Test that error sections extraction works."""
    content = """
    Some normal text.
    Traceback (most recent call last):
      File "test.py", line 1, in <module>
        raise ValueError("test")
    ValueError: test
    
    Another error: Something went wrong.
    """
    
    sections = ContentExtractor.extract_error_sections(content)
    assert len(sections) > 0
    assert any("Traceback" in s for s in sections)
    assert any("Error:" in s for s in sections)


def test_content_extractor_tool_sections():
    """Test that tool sections extraction works."""
    content = """
    Some normal text.
    Tool call: read_file {"path": "test.txt"}
    Another tool call: write_file {"path": "output.txt", "content": "hello"}
    """
    
    sections = ContentExtractor.extract_tool_sections(content)
    assert len(sections) > 0
    assert any("Tool call" in s for s in sections)


def test_intelligent_context_manager_initialization():
    """Test that IntelligentContextManager can be initialized."""
    config = IntelligentContextConfig(
        max_tokens=8000,
        max_protected_ratio=0.3,
        importance_threshold=0.5,
        cluster_similarity_threshold=0.7,
        adaptive_compression=True,
    )
    
    manager = IntelligentContextManager(config)
    assert manager.config == config


def test_token_counting():
    """Test token counting functionality."""
    messages = [
        Message(role="user", content="Hello, world!"),
        Message(role="assistant", content="Hi there!"),
    ]
    
    config = IntelligentContextConfig()
    manager = IntelligentContextManager(config)
    
    # This should not raise an error
    token_count = manager._count_tokens(messages)
    assert isinstance(token_count, int)
    assert token_count >= 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])