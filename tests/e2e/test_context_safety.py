

import pytest

from henchman.providers.base import Message, ToolCall
from henchman.tools.builtins.glob_tool import GlobTool
from henchman.tools.builtins.shell import ShellTool
from henchman.utils.compaction import ContextCompactor


@pytest.mark.asyncio
class TestContextSafety:

    async def test_shell_tool_truncation(self):
        """Test that ShellTool truncates excessive output."""
        tool = ShellTool()
        limit = tool.MAX_OUTPUT_CHARS

        # Create a command that produces massive output
        # Using python -c to generate it
        cmd = f"python3 -c 'print(\"a\" * {limit + 1000})'"

        result = await tool.execute(command=cmd)

        assert result.success
        assert len(result.content) < limit + 200  # Allow for "truncated" message
        assert "output truncated" in result.content
        assert len(result.content) <= limit + len(f"\n... (output truncated after {limit} chars)")

    async def test_glob_tool_truncation(self, tmp_path):
        """Test that GlobTool truncates matching list."""
        tool = GlobTool()
        limit = tool.MAX_MATCHES

        # Create more files than the limit
        test_dir = tmp_path / "glob_test"
        test_dir.mkdir()

        for i in range(limit + 50):
            (test_dir / f"test_{i}.txt").touch()

        result = await tool.execute(pattern="*.txt", path=str(test_dir))

        assert result.success
        assert "Output truncated" in result.content
        assert f"limit reached: {limit} matches" in result.content

        # Count lines (excluding the truncation message)
        lines = result.content.splitlines()
        # The last line is the truncation message
        assert len(lines) == limit + 1
        assert lines[-1].startswith("... Output truncated")

    def test_compactor_safety_limit(self):
        """Test that ContextCompactor enforces limits on individual messages."""
        # Use token limit large enough to fit overhead but small enough to test truncation
        limit_tokens = 300
        compactor = ContextCompactor(max_tokens=limit_tokens)
        
        # Limit will be 0.9 * 300 = 270 tokens
        # Create a message exceeding the limit 
        # "word " is 1 token. We want > 270 tokens.
        huge_content = "word " * 500
        messages = [
            Message(role="system", content="System prompt"),
            Message(role="user", content="Here is a huge message:"),
            Message(role="assistant", content=huge_content)
        ]
        
        # Run compaction (which includes safety check)
        compacted = compactor.compact(messages)
        
        # Check that the huge message was truncated
        # With max_tokens=300, limit is 270.
        # Total tokens should be ~290 < 300. So all messages should be kept.
        assert len(compacted) == 3
        huge_msg = compacted[2]
        assert len(huge_msg.content) < len(huge_content)
        assert "truncated by safety limit" in huge_msg.content
        
        # Check other messages are untouched
        assert compacted[0].content == "System prompt"
        assert compacted[1].content == "Here is a huge message:"

    async def test_compactor_safety_limit_preserves_tool_calls(self):
        """Test that safety limit preserves tool call structure even if content is truncated."""
        # Use token limit large enough to fit overhead
        limit_tokens = 300
        compactor = ContextCompactor(max_tokens=limit_tokens)
        
        huge_content = "word " * 500
        
        tool_call = ToolCall(id="call_1", name="test_tool", arguments={})
        
        messages = [
            Message(role="assistant", tool_calls=[tool_call], content=huge_content)
        ]
        
        compacted = compactor.compact(messages)
        
        msg = compacted[0]
        assert len(msg.content) < len(huge_content)
        assert "truncated" in msg.content
        # Ensure other attributes are preserved
        assert msg.tool_calls == [tool_call]
