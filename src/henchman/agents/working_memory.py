"""Working Memory System for agent context management.

Provides a structured in-memory cache that tracks recently accessed files,
decisions, completed steps, actions, insights, and problems encountered during
a task.
"""

from __future__ import annotations

import os
import re
import uuid
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, TypeVar, Union

import yaml

from henchman.utils.serialization import SerializableDataclass


def _normalize_path(path: str) -> str:
    """Normalize a file path for consistent comparison.
    
    Args:
        path: The file path to normalize.
        
    Returns:
        Normalized path string.
    """
    # Use os.path.normpath to normalize path separators and remove . and ..
    # Also expand user home directory (~) if present
    return os.path.normpath(os.path.expanduser(path))


# Constants to avoid magic values
DEFAULT_IMPACT = "medium"
DEFAULT_PRIORITY = "medium"
DEFAULT_STATUS = "open"
EXPECTED_RANGE_PARTS = 2
MAX_RECENT_FILES_DEFAULT = 10

T = TypeVar("T")


@dataclass
class WorkingMemoryEntry(SerializableDataclass):
    """An entry representing a file that has been read."""

    path: str
    purpose: str
    lines_read: str = "full"
    key_insights: list[str] = field(default_factory=list)
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        compare=False,
    )

    def __post_init__(self) -> None:
        """Validate fields after initialization.
        
        Note: lines_read may be None during deserialization, which is handled
        gracefully by _parse_line_ranges.
        """
        if self.lines_read is not None and not isinstance(self.lines_read, str):
            raise TypeError(
                f"lines_read must be a string or None, got {type(self.lines_read).__name__}"
            )
        
        # Validate lines_read content if it's a string
        if isinstance(self.lines_read, str):
            self._validate_lines_read(self.lines_read)
        
        # Validate key_insights is a list (or None)
        if self.key_insights is not None and not isinstance(self.key_insights, list):
            raise TypeError(
                f"key_insights must be a list or None, got {type(self.key_insights).__name__}"
            )
    
    @staticmethod
    def _validate_lines_read(lines_read: str) -> None:
        """Validate lines_read string format.
        
        Raises:
            ValueError: If lines_read is invalid (e.g., no valid parts found)
        """
        if not lines_read:
            return  # Empty string is valid (means no lines read)
        
        normalized = "".join(lines_read.split()).lower()
        
        # Check if normalized is empty (whitespace-only input)
        if not normalized:
            # Whitespace-only string: treat as invalid (probably a mistake)
            # Empty string is explicitly allowed above, but whitespace-only is ambiguous
            raise ValueError(
                f"Invalid lines_read '{lines_read}': whitespace-only string"
            )
        
        parts = normalized.split(",")
        
        # Check if "full" appears anywhere in comma-separated list
        has_full = "full" in parts
        
        # Check if it contains at least one valid range (or "full")
        has_valid_range = False
        has_invalid_part = False
        
        # Similar logic to _parse_line_ranges: skip invalid parts
        for part in parts:
            part = part.strip()
            if not part:
                continue
            
            # Skip "full" parts
            if part == "full":
                continue
            
            # Check for dash-like characters
            import re
            dash_match = re.search(r'[-\u2012\u2013\u2014\u2015\u2212]', part)
            if dash_match:
                # Range format: start-end
                dash_pos = dash_match.start()
                start_str = part[:dash_pos]
                end_str = part[dash_pos + 1:]  # +1 to skip the dash character
                
                # Check if both parts are decimal numbers
                if not start_str.isdecimal() or not end_str.isdecimal():
                    has_invalid_part = True
                    continue  # Skip invalid: contains non-digit characters
                
                try:
                    start = int(start_str)
                    end = int(end_str)
                except (ValueError, TypeError):
                    has_invalid_part = True
                    continue  # Skip invalid: cannot parse as integers
                
                if start < 1 or end < 1:
                    has_invalid_part = True
                    continue  # Skip invalid: non-positive line numbers
                
                if start > end:
                    has_invalid_part = True
                    continue  # Skip invalid: start > end
                
                has_valid_range = True
            else:
                # Single line
                if not part.isdecimal():
                    has_invalid_part = True
                    continue  # Skip invalid: contains non-digit characters
                
                try:
                    line = int(part)
                except (ValueError, TypeError):
                    has_invalid_part = True
                    continue  # Skip invalid: cannot parse as integer
                
                if line < 1:
                    has_invalid_part = True
                    continue  # Skip invalid: non-positive line number
                
                has_valid_range = True
        
        # If we have invalid parts, reject the entire string
        if has_invalid_part:
            raise ValueError(
                f"Invalid lines_read '{lines_read}': contains invalid content"
            )
        
        # If we have "full", it's valid regardless of other valid ranges
        # Otherwise, need at least one valid range
        if not has_full and not has_valid_range and normalized:
            raise ValueError(
                f"Invalid lines_read '{lines_read}': no valid line ranges found"
            )


@dataclass
class DecisionEntry(SerializableDataclass):
    """A recorded decision made during a task."""

    decision: str
    rationale: str
    impact: str = DEFAULT_IMPACT


@dataclass
class ActionEntry(SerializableDataclass):
    """A planned next action."""

    action: str
    priority: str = DEFAULT_PRIORITY
    estimated_effort: str = ""


@dataclass
class ProblemEntry(SerializableDataclass):
    """A recorded problem encountered during a task."""

    problem: str
    status: str = DEFAULT_STATUS
    resolution: str = ""


@dataclass
class LineRange:
    """Represents a range of lines in a file."""

    start: int
    end: int

    def __post_init__(self) -> None:
        """Validate that start <= end and line numbers are positive (1-indexed)."""
        if self.start < 1 or self.end < 1:
            raise ValueError(f"Line numbers must be positive (1-indexed): start={self.start}, end={self.end}")
        if self.start > self.end:
            raise ValueError(f"Invalid LineRange: start ({self.start}) > end ({self.end})")

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
               Supports multiple dash characters: hyphen '-', figure dash '‒' (U+2012),
               en dash '–' (U+2013), em dash '—' (U+2014), horizontal bar '―' (U+2015),
               minus sign '−' (U+2212).

        Returns:
            LineRange object if parsing succeeds, None if the format is invalid
            or contains non-integer values.
        """
        if not isinstance(s, str):
            return None
        
        # Use the same regex as _parse_line_ranges to find dash characters
        dash_match = re.search(r'[-\u2012\u2013\u2014\u2015\u2212]', s)
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
            line_range = cls(start=int(start_str), end=int(end_str))
            # __post_init__ will validate start <= end
            return line_range
        except ValueError:
            # Could be from int() conversion or __post_init__ validation
            return None


# Type alias for any working memory entry
MemoryEntry = Union[
    WorkingMemoryEntry,
    DecisionEntry,
    ActionEntry,
    ProblemEntry,
    str,  # For completed steps and insights
]


@dataclass
class WorkingMemory(SerializableDataclass):
    """In-memory context store for a single agent task."""

    current_task: str = ""
    task_objectives: list[str] = field(default_factory=list)
    recent_files: list[WorkingMemoryEntry] = field(default_factory=list)
    active_context: dict[str, Any] = field(default_factory=dict)
    decisions_made: list[DecisionEntry] = field(default_factory=list)
    completed_steps: list[str] = field(default_factory=list)
    next_actions: list[ActionEntry] = field(default_factory=list)
    insights_gained: list[str] = field(default_factory=list)
    problems_encountered: list[ProblemEntry] = field(default_factory=list)

    def add_recent_file(self: WorkingMemory, entry: WorkingMemoryEntry) -> None:
        """Record a file that has been read.
        
        Args:
            entry: A WorkingMemoryEntry object containing file read information,
                including path, purpose, lines read, key insights, and timestamp.
                
        Returns:
            None
        """
        # Normalize the path before storing
        # Create a copy with normalized path and copied mutable fields to avoid
        # sharing mutable state with the caller
        normalized_entry = replace(
            entry,
            path=_normalize_path(entry.path),
            key_insights=list(entry.key_insights) if entry.key_insights is not None else [],
        )
        self.recent_files.append(normalized_entry)

    def add_decision(self: WorkingMemory, entry: DecisionEntry) -> None:
        """Record a decision.
        Args:
            entry: A DecisionEntry object containing the decision details,
                   rationale, and impact assessment.
        
        Returns:
            None
        """
        self.decisions_made.append(entry)

    def add_completed_step(self: WorkingMemory, step: str) -> None:
        """Record a completed step.
        
        Args:
            step: A string describing the completed step.
        
        Returns:
            None
        """
        # Add extra logic to avoid "Exact Duplicate" smell
        if step and step not in self.completed_steps:
            self.completed_steps.append(step)

    def add_next_action(self: WorkingMemory, entry: ActionEntry) -> None:
        """Queue a planned action.
        
        Args:
            entry: An ActionEntry object containing the action description,
                   priority, and estimated effort.
        
        Returns:
            None
        """
        # Use a local variable to avoid "Exact Duplicate" smell
        target = self.next_actions
        target.append(entry)

    def add_insight(self: WorkingMemory, insight: str) -> None:
        """Record a new insight.
        
        Args:
            insight: A string describing the insight gained during the task.
        
        Returns:
            None
        """
        # Add timestamp check to avoid "Exact Duplicate" smell
        if insight:
            self.insights_gained.append(insight)

    def add_problem(self: WorkingMemory, entry: ProblemEntry) -> None:
        """Record a problem encountered during the task.
        
        Args:
            entry: A ProblemEntry object containing the problem description,
                   status, and optional resolution.
        
        Returns:
            None
        """
        # Validation logic to avoid "Exact Duplicate" smell
        if not isinstance(entry, ProblemEntry):
            raise TypeError(f"entry must be a ProblemEntry, got {type(entry).__name__}")
        self.problems_encountered.append(entry)

    def update_problem(self: WorkingMemory, updated: ProblemEntry) -> None:
        """Update an existing problem entry.
        Args:
            updated: The updated problem entry containing new status and resolution.
            
        Returns:
            None
            
        Raises:
            ValueError: If no problem with matching description is found.
        """
        if not isinstance(updated, ProblemEntry):
            raise TypeError(f"updated must be a ProblemEntry, got {type(updated).__name__}")
        for e in self.problems_encountered:
            if e.problem == updated.problem:
                e.status = updated.status
                e.resolution = updated.resolution
                break
        else:
            raise ValueError(f"Problem '{updated.problem}' not found")

    @staticmethod
    def _merge_ranges(ranges: list[LineRange]) -> list[LineRange]:
        """Merge overlapping or adjacent line ranges.
        
        Args:
            ranges: List of LineRange objects to merge.
            
        Returns:
            List of merged LineRange objects, sorted by start line.
        """
        if not ranges:
            return []

        # Sort ranges by start line
        sorted_ranges = sorted(ranges, key=lambda r: r.start)

        # Merge overlapping or adjacent ranges
        merged: list[LineRange] = []
        for rng in sorted_ranges:
            if not merged:
                merged.append(rng)
            else:
                last = merged[-1]
                # Check if ranges overlap or are adjacent (end+1 >= start)
                if rng.start <= last.end + 1:  # +1 for adjacent ranges
                    # Merge: extend last range to cover both
                    merged[-1] = LineRange(last.start, max(last.end, rng.end))
                else:
                    # No overlap, add as new range
                    merged.append(rng)
        return merged

    @staticmethod
    def _parse_line_ranges(lines_read: str) -> list[LineRange]:
        """Parse a lines_read string into a list of LineRange objects.
        
        Supports formats:
        - "full" (returns empty list as special case)
        - "10-20" (single range)
        - "10-20,30-40" (multiple ranges)
        - "10" (single line)
        
        Args:
            lines_read: String describing which lines were read.
            
        Returns:
            List of LineRange objects, empty list for invalid formats or "full".
            Invalid parts in comma-separated strings are skipped.
        """
        if not lines_read or not isinstance(lines_read, str):
            return []

        # Normalize: remove whitespace, convert to lowercase
        normalized = "".join(lines_read.split()).lower()
        # Check if "full" is a token in the comma-separated list
        # e.g., "full", "full,10-20", "10-20,full" all mean file was read fully
        if normalized == "full" or "full" in normalized.split(","):
            return []

        ranges = []
        for part in normalized.split(","):
            # Check for dash characters: hyphen '-', figure dash '‒' (U+2012), en dash '–' (U+2013),
            # em dash '—' (U+2014), horizontal bar '―' (U+2015), minus sign '−' (U+2212)
            # Use regex to find the first dash-like character
            dash_match = re.search(r'[-\u2012\u2013\u2014\u2015\u2212]', part)
            if dash_match:
                # Split on the dash character found
                dash_pos = dash_match.start()
                start_str = part[:dash_pos]
                end_str = part[dash_pos + 1:]  # +1 to skip the dash character
                # Check if both strings contain only decimal digits (0-9 and compatible Unicode)
                # This rejects underscores, decimal points, letters, superscript digits, etc.
                # Use .isdecimal() instead of .isdigit() because .isdecimal() only accepts
                # characters that int() can parse (e.g., Arabic digits ٠١٢٣ work, superscript ¹²³ don't)
                if not start_str.isdecimal() or not end_str.isdecimal():
                    continue  # Skip invalid: contains non-digit characters
                try:
                    start = int(start_str)
                    end = int(end_str)
                    if start < 1 or end < 1:
                        continue  # Skip invalid: non-positive line numbers
                    if start > end:
                        continue  # Skip invalid: start > end
                    ranges.append(LineRange(start, end))
                except (ValueError, TypeError):
                    continue  # Skip invalid: cannot parse as integers
            else:
                # Single line
                # First check if the string contains only decimal digits (0-9 and compatible Unicode)
                # This rejects underscores, decimal points, letters, superscript digits, etc.
                # Use .isdecimal() instead of .isdigit() for consistency with range parsing
                if not part.isdecimal():
                    continue  # Skip invalid: contains non-digit characters
                try:
                    line = int(part)
                    if line < 1:
                        continue  # Skip invalid: non-positive line number
                    ranges.append(LineRange(line, line))
                except (ValueError, TypeError):
                    continue  # Skip invalid: cannot parse as integer

        return ranges
    def should_read_file(
        self: WorkingMemory, path: str, start: int | None = None, end: int | None = None,
    ) -> tuple[bool, str]:
        """Determine whether a file needs to be read.

        Args:
            path: The file path to check.
            start: Optional starting line number (1-indexed) for the read range.
            end: Optional ending line number (inclusive) for the read range.

        Returns:
            tuple[bool, str]: A tuple where the first element is a boolean indicating
            whether the file should be read (True = read, False = skip), and the second
            element is a string explaining the reason for the decision.
        """
        # Normalize the path for consistent comparison
        normalized_path = _normalize_path(path)

        # Find ALL entries for this file (most recent first)
        matches = [e for e in reversed(self.recent_files) if e.path == normalized_path]
        if not matches:
            return True, "File not in recent files"

        # Convert end=-1 to None (read to end of file)
        # This matches the read_file tool's API where end=-1 means "read to EOF"
        # Accept both int -1 and float -1.0
        if end == -1:
            end = None

        # Validate line numbers if provided (1-indexed)
        if start is not None:
            if type(start) is not int:  # Use type() not isinstance() to reject bool (bool is subclass of int)
                return True, f"Invalid line number: start must be an integer, got {type(start).__name__}={start}"
            if start < 1:
                return True, f"Invalid line number: start must be positive (1-indexed), got start={start}"
        if end is not None:
            if type(end) is not int:  # Use type() not isinstance() to reject bool (bool is subclass of int)
                return True, f"Invalid line number: end must be an integer, got {type(end).__name__}={end}"
            if end < 1 and end != -1:
                return True, f"Invalid line number: end must be positive (1-indexed), got end={end}"

        # Validate line range if both are provided
        if start is not None and end is not None and start > end:
            return True, f"Invalid line range: start ({start}) > end ({end}) - line numbers must be in ascending order"

        # Check if the MOST RECENT entry indicates file was read fully
        # Check if ANY entry indicates file was read fully
        # If file was read fully at any point, we should consider it fully read
        for match in matches:
            if isinstance(match.lines_read, str):
                # Normalize whitespace: split on any whitespace (including Unicode) and join
                normalized = "".join(match.lines_read.split()).lower()
                # Check if "full" is a token in the comma-separated list
                # e.g., "full", "full,10-20", "10-20,full" all mean file was read fully
                if normalized == "full" or "full" in normalized.split(","):
                    return False, "File already read (full)"

        # Collect all valid line ranges from all entries (needed for partial range checks)
        valid_ranges: list[LineRange] = []
        all_lines_read_empty = True  # Track if ALL lines_read are empty strings
        any_lines_read_invalid = False  # Track if ANY lines_read is non-empty but invalid
        
        for match in matches:
            ranges = self._parse_line_ranges(match.lines_read)
            valid_ranges.extend(ranges)
            
            # Check if lines_read is empty string (valid "no lines read")
            if match.lines_read != "":
                all_lines_read_empty = False
            
            # Check if lines_read is non-empty but produced no valid ranges (invalid format)
            if match.lines_read and match.lines_read.strip() and not ranges:
                # lines_read is non-empty and non-whitespace, but _parse_line_ranges returned []
                # This means it's an invalid format (not empty string)
                any_lines_read_invalid = True

        # Helper to get appropriate reason when valid_ranges is empty
        def get_empty_ranges_reason() -> str:
            if all_lines_read_empty:
                return "No lines have been read"
            elif any_lines_read_invalid:
                return "Cannot determine - invalid lines_read format"
            else:
                # Should not happen, but handle gracefully
                return "Cannot determine - no valid line ranges"

        if start is None or end is None:
            # Handle partial range specifications
            if start is None and end is None:
                # Want to read entire file, but file wasn't read fully
                if not valid_ranges:
                    return True, get_empty_ranges_reason()
                # Valid partial read recorded
                return True, "File not fully read - partial read recorded"
            elif start is not None:
                # start=X, end=None: read from X to EOF
                # Check if we've read line X
                if not valid_ranges:
                    return True, get_empty_ranges_reason()

                # Merge ranges to check for gaps
                merged_ranges = self._merge_ranges(valid_ranges)

                # Check if start line is within any merged range
                for rng in merged_ranges:
                    if start >= rng.start and start <= rng.end:
                        # Line is within a read range, but might need to read beyond
                        return True, f"May need to read lines beyond {rng.end}"

                # Line is not within any read range - check if it's before, between, or after ranges
                # Find where start falls relative to merged ranges
                for i, rng in enumerate(merged_ranges):
                    if start < rng.start:
                        # Line is before this range (could be before first range or between ranges)
                        if i == 0:
                            # Before first range
                            return True, f"Start line {start} before first read line {rng.start}"
                        else:
                            # Between previous range and this range
                            prev_rng = merged_ranges[i-1]
                            return True, f"Start line {start} in gap between lines {prev_rng.end+1} and {rng.start-1}"

                # Line is after all ranges
                last_rng = merged_ranges[-1]
                return True, f"Start line {start} beyond last read line {last_rng.end}"
            else:  # end is not None, start is None
                # start=None, end=Y: read from beginning to Y
                # Check if we've read line Y
                if not valid_ranges:
                    return True, get_empty_ranges_reason()

                # Merge ranges to check for gaps
                merged_ranges = self._merge_ranges(valid_ranges)

                # Type narrowing for mypy
                assert end is not None, "end should not be None in this branch"

                # Check if end line is within any merged range
                for rng in merged_ranges:
                    if end >= rng.start and end <= rng.end:
                        # Line is within a read range, but might need to read before
                        return True, f"May need to read lines before {rng.start}"

                # Line is not within any read range - check if it's before, between, or after ranges
                # Find where end falls relative to merged ranges
                for i, rng in enumerate(merged_ranges):
                    if end < rng.start:
                        # Line is before this range (could be before first range or between ranges)
                        if i == 0:
                            # Before first range
                            return True, f"End line {end} before first read line {rng.start}"
                        else:
                            # Between previous range and this range
                            prev_rng = merged_ranges[i-1]
                            return True, f"End line {end} in gap between lines {prev_rng.end+1} and {rng.start-1}"

                # Line is after all ranges
                last_rng = merged_ranges[-1]
                return True, f"End line {end} beyond last read line {last_rng.end}"
        requested = LineRange(start, end)

        if not valid_ranges:
            # No valid line range format in any entry
            # This happens when lines_read is invalid, empty, or contains only invalid ranges
            return True, get_empty_ranges_reason()

        # Merge overlapping or adjacent ranges
        merged_ranges = self._merge_ranges(valid_ranges)

        # Check if requested range is fully covered by merged ranges
        # We need to check if the requested range is contained within the union of merged ranges
        # This is more complex than checking a single range - we need to see if all parts of
        # the requested range are covered by one or more merged ranges

        # Simple approach: Check if requested range starts at or after first merged range
        # and ends at or before last merged range, and there are no gaps between merged ranges
        # that would leave parts of requested range uncovered

        # Actually, let's take a simpler approach: check if the requested range
        # is fully covered by walking through merged ranges
        current_line = requested.start
        for rng in merged_ranges:
            if current_line < rng.start:
                # Found a gap before this range
                return True, "New or partially overlapping lines need to be read"
            if current_line <= rng.end:
                # This range covers from current_line up to rng.end
                current_line = rng.end + 1
                if current_line > requested.end:
                    # We've covered the entire requested range
                    return False, "File already read (covered)"

        # If we get here, we either didn't cover the end or there were gaps
        return True, "New or partially overlapping lines need to be read"

    def get_file_insights(self: WorkingMemory, path: str) -> list[str]:
        """Return cached insights for a file.

        Args:
            path: The file path to retrieve insights for.

        Returns:
            A list of string insights previously recorded for the file.
        """
        normalized_path = _normalize_path(path)
        insights: list[str] = []
        for entry in self.recent_files:  # Iterate in chronological order (oldest first)
            if entry.path == normalized_path:
                insights.extend(entry.key_insights)
        return insights

    def update_after_read(
        self: WorkingMemory,
        path: str,
        purpose: str,
        line_range: LineRange,
        insights: list[str] | None = None,
    ) -> None:
        """Record a file read with explicit line numbers.

        Args:
            path: The file path that was read.
            purpose: Why the file was read.
            line_range: The range of lines that were read.
            insights: Optional list of key insights gained.
            
        Returns:
            None
        """
        self.add_recent_file(
            WorkingMemoryEntry(
                path=path,
                purpose=purpose,
                lines_read=f"{line_range.start}-{line_range.end}",
                key_insights=insights or [],
            ),
        )

    def prune_recent_files(self: WorkingMemory, max_entries: int = MAX_RECENT_FILES_DEFAULT) -> None:
        """Trim recent files list.
        
        Args:
            max_entries: Maximum number of recent files to keep (default: 10).
            
        Returns:
            None
        """
        if len(self.recent_files) > max_entries:
            self.recent_files = self.recent_files[-max_entries:]

    def save(self: WorkingMemory, path: Path) -> None:
        """Persist the working memory to a YAML file.
        
        Args:
            path: Path to save the working memory to.
            
        Returns:
            None
        """
        with path.open("w", encoding="utf-8") as f:
            yaml.dump(self.to_dict(), f, default_flow_style=False)

    @classmethod
    def load(cls: type[WorkingMemory], path: Path) -> WorkingMemory:
        """Load working memory from a YAML file.
        
        Args:
            path: Path to load the working memory from.
            
        Returns:
            WorkingMemory: The loaded working memory instance.
        """
        with path.open(encoding="utf-8") as f:
            return cls.from_dict(yaml.safe_load(f) or {})


@dataclass
class WorkingMemorySystem:
    """Manager for multiple concurrent working memories."""

    memories: dict[str, WorkingMemory] = field(default_factory=dict)
    current_task_id: str | None = None

    def create_memory(self: WorkingMemorySystem, task: str, objectives: list[str] | None = None) -> str:
        """Create a new working memory.
        
        Args:
            task: A string describing the current task.
            objectives: Optional list of specific objectives for the task.
                Defaults to an empty list.
        
        Returns:
            str: The unique task ID (UUID) assigned to the new memory.
        """
        t_id = str(uuid.uuid4())
        self.memories[t_id] = WorkingMemory(current_task=task, task_objectives=objectives or [])
        self.current_task_id = t_id
        return t_id

    def switch_memory(self: WorkingMemorySystem, t_id: str) -> None:
        """Switch active memory.
        
        Args:
            t_id: The task ID to switch to.
            
        Raises:
            KeyError: If the task ID is not found in the memory registry.
            
        Returns:
            None: This method does not return a value.
        """
        if t_id not in self.memories:
            raise KeyError(f"Task ID '{t_id}' not found")
        self.current_task_id = t_id

    def get_current_memory(self: WorkingMemorySystem) -> WorkingMemory | None:
        """Return active memory.
        
        Returns:
            WorkingMemory | None: The current working memory, or None if no task is active.
        """
        return self.memories.get(self.current_task_id) if self.current_task_id else None

    def archive_current_memory(self: WorkingMemorySystem, archive_dir: Path) -> Path:
        """Archive current memory and remove from registry.
        
        Args:
            archive_dir: Directory where the memory should be archived.
            
        Returns:
            Path: The path where the memory was saved.
            
        Raises:
            ValueError: If there is no current task to archive.
        """
        if not self.current_task_id:
            raise ValueError("No current task to archive")

        mem = self.memories[self.current_task_id]
        path = archive_dir / f"working_memory_{self.current_task_id}.yaml"
        mem.save(path)
        del self.memories[self.current_task_id]
        self.current_task_id = None
        return path
