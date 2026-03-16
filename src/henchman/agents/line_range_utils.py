"""LineRange and related utilities for working memory system.

This module contains the LineRange dataclass and utility functions for parsing,
merging, and working with line ranges.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class LineRange:
    """Represents a range of lines in a file."""

    start: int
    end: int

    def __post_init__(self: LineRange) -> None:
        """Validate that start <= end and line numbers are positive (1-indexed)."""
        if self.start < 1 or self.end < 1:
            msg = f"Line numbers must be positive (1-indexed): start={self.start}, end={self.end}"
            raise ValueError(msg)
        if self.start > self.end:
            msg = f"Invalid LineRange: start ({self.start}) > end ({self.end})"
            raise ValueError(msg)

    def overlaps(self: LineRange, other: LineRange) -> bool:
        """Check if this line range overlaps with another.

        Args:
            other: Another LineRange to check for overlap with.

        Returns:
            True if the line ranges overlap (share at least one line in common),
            False otherwise.
        """
        return self.start <= other.end and self.end >= other.start

    @classmethod
    def from_str(cls: type[LineRange], s: str) -> LineRange | None:
        """Parse a "start-end" line range string.

        Args:
            s: String in format "start-end" where start and end are integers,
               e.g., "1-10", "5-25". The dash separator is required.
               Supports multiple dash characters: hyphen (U+002D), figure dash (U+2012),
               en dash (U+2013), em dash (U+2014), horizontal bar (U+2015),
               minus sign (U+2212).

        Returns:
            LineRange object if parsing succeeds, None if the format is invalid
            or contains non-integer values.
        """
        if not isinstance(s, str):
            return None

        # Use the same regex as _parse_line_ranges to find dash characters
        dash_match = re.search(r"[-\u2012\u2013\u2014\u2015\u2212]", s)
        if not dash_match:
            return None

        # Split on the dash character found
        dash_pos = dash_match.start()
        start_str = s[:dash_pos]
        end_str = s[dash_pos + 1:]  # +1 to skip the dash character

        # Check if both strings contain only decimal digits (0-9 and compatible Unicode)
        # This rejects underscores, decimal points, letters, superscript digits, etc.
        # Use .isdecimal() instead of .isdigit() for consistency with _parse_line_ranges
        if not start_str.isdecimal() or not end_str.isdecimal():
            return None

        try:
            return cls(start=int(start_str), end=int(end_str))
            # __post_init__ will validate start <= end
        except ValueError:
            # Could be from int() conversion or __post_init__ validation
            return None


def merge_line_ranges(ranges: list[LineRange]) -> list[LineRange]:
    """Merge overlapping or adjacent line ranges.

    Args:
        ranges: List of LineRange objects to merge.

    Returns:
        List of merged LineRange objects, sorted by start line.
    """
    if not ranges:
        return []

    # Sort by start line
    sorted_ranges = sorted(ranges, key=lambda r: r.start)
    merged: list[LineRange] = []

    current = sorted_ranges[0]
    for next_range in sorted_ranges[1:]:
        # Check if ranges overlap or are adjacent (end+1 == start)
        if current.end + 1 >= next_range.start:
            # Merge: extend current range if next_range.end is larger
            if next_range.end > current.end:
                current = LineRange(current.start, next_range.end)
        else:
            # No overlap or adjacency, add current to merged list
            merged.append(current)
            current = next_range

    # Add the last range
    merged.append(current)
    return merged


def _parse_range_part(part: str) -> LineRange | None:
    """Parse a single range part (start-end format).

    Args:
        part: String in format "start-end".

    Returns:
        LineRange object if valid, None if invalid.
    """
    dash_match = re.search(r"[-\u2012\u2013\u2014\u2015\u2212]", part)
    if not dash_match:
        return None

    dash_pos = dash_match.start()
    start_str = part[:dash_pos]
    end_str = part[dash_pos + 1:]  # +1 to skip the dash character

    if not start_str.isdecimal() or not end_str.isdecimal():
        return None

    try:
        start, end = int(start_str), int(end_str)
    except (ValueError, TypeError):
        return None

    if start < 1 or end < 1 or start > end:
        return None

    try:
        return LineRange(start, end)
    except ValueError:
        return None


def _parse_single_line_part(part: str) -> LineRange | None:
    """Parse a single line part.

    Args:
        part: String representing a single line number.

    Returns:
        LineRange object if valid, None if invalid.
    """
    if not part.isdecimal():
        return None

    try:
        line = int(part)
    except (ValueError, TypeError):
        return None

    if line < 1:
        return None

    try:
        return LineRange(line, line)
    except ValueError:
        return None


def _parse_parts(parts: list[str]) -> list[LineRange]:
    """Parse individual comma-split parts into LineRange objects.

    Args:
        parts: List of strings from splitting the normalized input on commas.

    Returns:
        List of valid LineRange objects parsed from the parts.
    """
    ranges: list[LineRange] = []
    for raw_part in parts:
        stripped = raw_part.strip()
        if not stripped:
            continue
        line_range = _parse_range_part(stripped) or _parse_single_line_part(stripped)
        if line_range is not None:
            ranges.append(line_range)
    return ranges


def parse_line_ranges(lines_read: str | None) -> list[LineRange]:
    """Parse a lines_read string into a list of LineRange objects.

    Args:
        lines_read: String describing which lines were read, or None.
            Format: comma-separated list of line ranges (e.g., "1-10,15-20")
            or single lines (e.g., "5,10,15"). "full" means entire file.
            Empty string or None means no lines read.

    Returns:
        List of LineRange objects. Returns empty list for:
        - None or empty string
        - "full" (treat as special case, no specific ranges)
        - Invalid format (silently ignored for backward compatibility)
    """
    if not lines_read:
        return []

    # Normalize: remove whitespace, convert to lowercase
    normalized = "".join(lines_read.split()).lower()

    if not normalized:
        return []

    parts = normalized.split(",")

    # "full" is a special case: treat as no specific ranges for compatibility
    # (the caller should handle "full" separately)
    if "full" in parts:
        return []

    return _parse_parts(parts)


def check_line_in_merged_ranges(
    line: int,
    merged_ranges: list[LineRange],
    prefix: str,
) -> tuple[bool, str]:
    """Check if a line is within, before, between, or after merged ranges.

    Args:
        line: The line number to check.
        merged_ranges: List of merged LineRange objects (sorted by start).
        prefix: String prefix for the reason ("Start" or "End").

    Returns:
        tuple[bool, str]: Whether to read and reason.
    """
    # Check if line is within any merged range
    for rng in merged_ranges:
        if line >= rng.start and line <= rng.end:
            # Line is within a read range, but might need to read beyond/before
            if prefix == "Start":
                return True, f"May need to read lines beyond {rng.end}"
            # "End"
            return True, f"May need to read lines before {rng.start}"

    # Line is not within any read range - check if it's before, between, or after ranges
    # Find where line falls relative to merged ranges
    for i, rng in enumerate(merged_ranges):
        if line < rng.start:
            # Line is before this range (could be before first range or between ranges)
            if i == 0:
                # Before first range
                return True, f"{prefix} line {line} before first read line {rng.start}"
            # Between previous range and this range
            prev_rng = merged_ranges[i-1]
            gap_start, gap_end = prev_rng.end + 1, rng.start - 1
            return True, f"{prefix} line {line} in gap between lines {gap_start} and {gap_end}"

    # Line is after all ranges
    last_rng = merged_ranges[-1]
    return True, f"{prefix} line {line} beyond last read line {last_rng.end}"
