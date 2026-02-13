"""Text chunking for RAG.

This module provides token-aware text chunking that preserves
code structure where possible.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import tiktoken


@dataclass
class Chunk:
    """A chunk of text from a file.

    Attributes:
        content: The text content of the chunk.
        file_path: Path to the source file.
        start_line: Starting line number (1-indexed).
        end_line: Ending line number (1-indexed, inclusive).
        chunk_index: Index of this chunk within the file.
    """

    content: str
    file_path: str
    start_line: int
    end_line: int
    chunk_index: int

    @property
    def id(self) -> str:
        """Generate a unique ID for this chunk.

        Returns:
            Unique identifier based on file path and chunk index.
        """
        return f"{self.file_path}::{self.chunk_index}"

    def to_metadata(self) -> dict[str, object]:
        """Convert to metadata dict for vector store.

        Returns:
            Dictionary with chunk metadata.
        """
        return {
            "file_path": self.file_path,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "chunk_index": self.chunk_index,
        }


class TextChunker:
    """Token-aware text chunker for code files.

    Splits text into chunks of approximately target_tokens size,
    with overlap for context continuity. Attempts to split at
    natural boundaries (blank lines, function definitions) when possible.

    Attributes:
        target_tokens: Target number of tokens per chunk.
        overlap_tokens: Number of overlapping tokens between chunks.
        encoding: Tiktoken encoding for token counting.
    """

    def __init__(
        self,
        target_tokens: int = 512,
        overlap_tokens: int = 50,
        encoding_name: str = "cl100k_base",
    ) -> None:
        """Initialize the text chunker.

        Args:
            target_tokens: Target number of tokens per chunk.
            overlap_tokens: Number of overlapping tokens between chunks.
            encoding_name: Tiktoken encoding name.
        """
        self.target_tokens = target_tokens
        self.overlap_tokens = overlap_tokens
        self.encoding = tiktoken.get_encoding(encoding_name)

    def count_tokens(self, text: str) -> int:
        """Count the number of tokens in text.

        Args:
            text: Text to count tokens for.

        Returns:
            Number of tokens.
        """
        return len(self.encoding.encode(text))

    def chunk_file(self, file_path: Path | str) -> list[Chunk]:
        """Chunk a file into pieces.

        Args:
            file_path: Path to the file to chunk.

        Returns:
            List of Chunk objects.
        """
        path = Path(file_path)
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            # Skip binary files
            return []

        return self.chunk_text(content, str(path))

    def chunk_text(self, text: str, file_path: str) -> list[Chunk]:
        """Chunk text content into pieces.

        Args:
            text: Text content to chunk.
            file_path: Path to associate with chunks.

        Returns:
            List of Chunk objects.
        """
        if not text.strip():
            return []

        lines = text.splitlines(keepends=True)
        chunks: list[Chunk] = []
        chunk_index = 0

        current_lines: list[str] = []
        current_start = 1
        current_tokens = 0

        for line_num, line in enumerate(lines, start=1):
            line_tokens = self.count_tokens(line)

            # Check if adding this line would exceed target
            if current_tokens + line_tokens > self.target_tokens and current_lines:
                # Create chunk from accumulated lines
                chunk_content = "".join(current_lines)
                chunks.append(
                    Chunk(
                        content=chunk_content,
                        file_path=file_path,
                        start_line=current_start,
                        end_line=line_num - 1,
                        chunk_index=chunk_index,
                    )
                )
                chunk_index += 1

                # Calculate overlap
                overlap_lines = self._get_overlap_lines(current_lines)
                if overlap_lines:
                    current_lines = overlap_lines
                    current_tokens = self.count_tokens("".join(current_lines))
                    current_start = line_num - len(overlap_lines)
                else:
                    current_lines = []
                    current_tokens = 0
                    current_start = line_num

            current_lines.append(line)
            current_tokens += line_tokens

        # Don't forget the last chunk
        if current_lines:
            chunk_content = "".join(current_lines)
            chunks.append(
                Chunk(
                    content=chunk_content,
                    file_path=file_path,
                    start_line=current_start,
                    end_line=len(lines),
                    chunk_index=chunk_index,
                )
            )

        return chunks

    def _get_overlap_lines(self, lines: list[str]) -> list[str]:
        """Get lines for overlap from the end of current chunk.

        Args:
            lines: Lines from the current chunk.

        Returns:
            Lines to include in overlap.
        """
        if not lines:
            return []

        overlap_lines: list[str] = []
        overlap_tokens = 0

        # Work backwards from the end
        for line in reversed(lines):
            line_tokens = self.count_tokens(line)
            if overlap_tokens + line_tokens > self.overlap_tokens:
                break
            overlap_lines.insert(0, line)
            overlap_tokens += line_tokens

        return overlap_lines
