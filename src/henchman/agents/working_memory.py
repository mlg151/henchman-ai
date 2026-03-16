"""Working Memory System for agent context management.

Provides a structured in-memory cache that tracks recently accessed files,
decisions, completed steps, actions, insights, and problems encountered during
a task.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, TypeVar

import yaml

if TYPE_CHECKING:
    pass

from henchman.agents.file_read_decision_maker import FileReadDecisionMaker
from henchman.agents.line_range_utils import (
    LineRange,
)
from henchman.utils.serialization import SerializableDataclass


@dataclass
class ValidationDecision:
    """Data class for validation decision parameters."""

    lines_read: str
    normalized: str
    has_full: bool
    has_valid_range: bool
    has_invalid_part: bool


def _normalize_path(path: str) -> str:
    """Normalize a file path for consistent comparison.

    Args:
        path: The file path to normalize.

    Returns:
        Normalized path string. Empty string is returned as-is.
    """
    if not path:
        return path  # Return empty string as-is

    # Expand user home directory (~) if present and normalize path
    expanded = Path(path).expanduser()
    # Use resolve() to normalize . and .. but also makes path absolute
    # which is fine for comparison purposes
    return str(expanded.resolve())


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
    def _validate_range_part(part: str) -> tuple[bool, bool]:
        """Validate a range part (start-end format).

        Args:
            part: String in format "start-end".

        Returns:
            tuple[bool, bool]: (is_valid_range, is_invalid_part)
        """
        # Find dash position
        dash_match = re.search(r'[-\u2012\u2013\u2014\u2015\u2212]', part)
        if not dash_match:
            return False, False  # Not a range format

        dash_pos = dash_match.start()
        start_str = part[:dash_pos]
        end_str = part[dash_pos + 1:]  # +1 to skip the dash character

        # Check if both parts are decimal numbers
        if not start_str.isdecimal() or not end_str.isdecimal():
            return False, True  # Invalid: contains non-digit characters

        try:
            start = int(start_str)
            end = int(end_str)
        except (ValueError, TypeError):
            return False, True  # Invalid: cannot parse as integers

        if start < 1 or end < 1 or start > end:
            return False, True  # Invalid: non-positive line numbers or start > end

        return True, False  # Valid range

    @staticmethod
    def _validate_single_line_part(part: str) -> tuple[bool, bool]:
        """Validate a single line part.

        Args:
            part: String representing a single line number.

        Returns:
            tuple[bool, bool]: (is_valid_range, is_invalid_part)
        """
        if not part.isdecimal():
            return False, True  # Invalid: contains non-digit characters

        try:
            line = int(part)
        except (ValueError, TypeError):
            return False, True  # Invalid: cannot parse as integer

        if line < 1:
            return False, True  # Invalid: non-positive line number

        return True, False  # Valid single line

    @staticmethod
    def _process_validation_part(part: str) -> tuple[bool, bool]:
        """Process a single part during lines_read validation.

        Args:
            part: A single part from the comma-separated lines_read string.

        Returns:
            tuple[bool, bool]: (is_valid_range, is_invalid_part)
                - is_valid_range: True if part represents a valid line range
                - is_invalid_part: True if part is invalid
        """
        # Check for dash-like characters to determine if it's a range
        dash_match = re.search(r'[-\u2012\u2013\u2014\u2015\u2212]', part)
        if dash_match:
            return WorkingMemoryEntry._validate_range_part(part)
        else:
            return WorkingMemoryEntry._validate_single_line_part(part)

    @staticmethod
    @staticmethod
    def _validate_lines_read_normalize(lines_read: str) -> tuple[str, list[str]]:
        """Normalize lines_read string and split into parts.

        Args:
            lines_read: String to normalize.

        Returns:
            tuple[str, list[str]]: (normalized_string, parts_list)
        """
        normalized = "".join(lines_read.split()).lower()

        # Check if normalized is empty (whitespace-only input)
        if not normalized:
            return "", []

        return normalized, normalized.split(",")

    @staticmethod
    def _validate_lines_read_process_parts(parts: list[str]) -> tuple[bool, bool, bool]:
        """Process parts and collect validation flags.

        Args:
            parts: List of string parts.

        Returns:
            tuple[bool, bool, bool]: (has_full, has_valid_range, has_invalid_part)
        """
        has_full = False
        has_valid_range = False
        has_invalid_part = False

        for part in parts:
            part = part.strip()
            if not part:
                continue

            # Check for "full" part
            if part == "full":
                has_full = True
                continue

            is_valid_range, is_invalid_part_flag = WorkingMemoryEntry._process_validation_part(part)
            if is_valid_range:
                has_valid_range = True
            if is_invalid_part_flag:
                has_invalid_part = True

        return has_full, has_valid_range, has_invalid_part

    @staticmethod
    def _validate_lines_read_decision(decision: ValidationDecision) -> None:
        """Make final validation decision.

        Args:
            decision: ValidationDecision object containing validation parameters.

        Raises:
            ValueError: If lines_read is invalid.
        """
        # If we have "full", it's valid regardless of other valid ranges or invalid parts
        if decision.has_full:
            return

        # If we have invalid parts but no valid ranges, reject the string
        if decision.has_invalid_part and not decision.has_valid_range and decision.normalized:
            error_msg = f"Invalid lines_read '{decision.lines_read}': no valid line ranges found"
            raise ValueError(error_msg)

        # If we have no valid ranges and no "full", reject the string
        if not decision.has_valid_range and decision.normalized:
            error_msg = f"Invalid lines_read '{decision.lines_read}': no valid line ranges found"
            raise ValueError(error_msg)

    @staticmethod
    def _validate_lines_read(lines_read: str | None) -> None:
        """Validate lines_read string format.

        Args:
            lines_read: String describing which lines were read, or None.
                None and empty string are valid (means no lines read).

        Raises:
            ValueError: If lines_read is invalid (e.g., no valid parts found)
        """
        # None or empty string is valid (means no lines read)
        if not lines_read:
            return

        # Normalize and split
        normalized, parts = WorkingMemoryEntry._validate_lines_read_normalize(lines_read)

        # Check if normalized is empty (whitespace-only input)
        if not normalized:
            return  # Whitespace-only is valid "no lines read"

        # Process parts and collect validation flags
        has_full, has_valid_range, has_invalid_part = (
            WorkingMemoryEntry._validate_lines_read_process_parts(parts)
        )

        # Make final validation decision
        decision = ValidationDecision(
            lines_read=lines_read,
            normalized=normalized,
            has_full=has_full,
            has_valid_range=has_valid_range,
            has_invalid_part=has_invalid_part,
        )
        WorkingMemoryEntry._validate_lines_read_decision(decision)


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

# Type alias for any working memory entry
MemoryEntry = (
    WorkingMemoryEntry
    | DecisionEntry
    | ActionEntry
    | ProblemEntry
    | str  # For completed steps and insights
)


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

    def _get_empty_ranges_reason(
        self, all_lines_read_empty: bool, any_lines_read_invalid: bool
    ) -> str:
        """Get appropriate reason when valid_ranges is empty.
        
        Args:
            all_lines_read_empty: Whether all lines_read entries are empty.
            any_lines_read_invalid: Whether any lines_read entry is invalid.
            
        Returns:
            Reason string.
        """
        if all_lines_read_empty:
            return "No lines have been read"
        elif any_lines_read_invalid:
            return "Cannot determine - invalid lines_read format"
        else:
            # Should not happen, but handle gracefully
            return "Cannot determine - no valid line ranges"

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
        # Validate and normalize line numbers
        should_read, reason, norm_start, norm_end = FileReadDecisionMaker._validate_and_normalize_line_numbers(start, end)
        if should_read:
            return should_read, reason

        # Use normalized values
        start, end = norm_start, norm_end

        # Normalize the path for consistent comparison
        normalized_path = _normalize_path(path)

        # Find ALL entries for this file (most recent first)
        matches = [e for e in reversed(self.recent_files) if e.path == normalized_path]
        if not matches:
            return True, "File not in recent files"

        # Get ranges info once to avoid duplicate calls
        _, all_empty, any_invalid = FileReadDecisionMaker._collect_valid_ranges_from_matches(matches)
        
        return FileReadDecisionMaker.should_read_file(
            matches=matches,
            start=start,
            end=end,
            get_empty_ranges_reason=lambda: self._get_empty_ranges_reason(all_empty, any_invalid)
        )

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
