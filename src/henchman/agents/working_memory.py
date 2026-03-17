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
from typing import Any, TypeVar

import yaml

from henchman.agents.file_read_decision_maker import (
    FileReadDecisionMaker,
    _collect_valid_ranges_from_matches,
    _validate_and_normalize_line_numbers,
)
from henchman.agents.line_range_utils import LineRange  # noqa: TC001
from henchman.utils.serialization import SerializableDataclass


@dataclass
class ValidationDecision:
    """Data class for validation decision parameters."""

    lines_read: str
    normalized: str
    has_full: bool
    has_valid_range: bool
    has_invalid_part: bool


@dataclass(frozen=True)
class EmptyRangesState:
    """Metadata about previously read line ranges for a file."""

    all_lines_read_empty: bool
    any_lines_read_invalid: bool


PathInput = str | Path

T = TypeVar("T")


def _normalize_path(path: PathInput) -> str:
    """Normalize a file path for consistent comparison.

    Args:
        path: The file path to normalize.

    Returns:
        Normalized path string. Empty string is returned as-is.
    """
    if isinstance(path, str):
        if not path:
            return path
        expanded = Path(path).expanduser()
    else:
        expanded = path.expanduser()

    # Use resolve() to normalize . and .. but also makes path absolute
    # which is fine for comparison purposes
    return str(expanded.resolve())


# Constants to avoid magic values
DEFAULT_IMPACT = "medium"
DEFAULT_PRIORITY = "medium"
DEFAULT_STATUS = "open"
EXPECTED_RANGE_PARTS = 2
MAX_RECENT_FILES_DEFAULT = 10


def _copy_insights(key_insights: list[str] | None) -> list[str]:
    """Return a defensive copy of key insights."""

    return list(key_insights) if key_insights is not None else []


def _type_error_message(field_name: str, expected: str, value: object) -> str:
    """Build a consistent type error message."""

    actual_type = type(value).__name__
    return f"{field_name} must be {expected}, got {actual_type}"


def _require_problem_entry(value: object, parameter_name: str) -> ProblemEntry:
    """Validate that a value is a ProblemEntry instance."""

    if isinstance(value, ProblemEntry):
        return value

    message = _type_error_message(parameter_name, "a ProblemEntry", value)
    raise TypeError(message)


def _validate_range_part(part: str) -> tuple[bool, bool]:
    """Validate a range part (start-end format).

    Args:
        part: String in format "start-end".

    Returns:
        tuple[bool, bool]: (is_valid_range, is_invalid_part)
    """
    dash_match = re.search(r"[-\u2012\u2013\u2014\u2015\u2212]", part)
    if not dash_match:
        return False, False  # Not a range format

    dash_pos = dash_match.start()
    start_str = part[:dash_pos]
    end_str = part[dash_pos + 1:]  # +1 to skip the dash character

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


def _process_validation_part(part: str) -> tuple[bool, bool]:
    """Process a single part during lines_read validation.

    Args:
        part: A single part from the comma-separated lines_read string.

    Returns:
        tuple[bool, bool]: (is_valid_range, is_invalid_part)
            - is_valid_range: True if part represents a valid line range
            - is_invalid_part: True if part is invalid
    """
    dash_match = re.search(r"[-\u2012\u2013\u2014\u2015\u2212]", part)
    if dash_match:
        return _validate_range_part(part)
    return _validate_single_line_part(part)


def _validate_lines_read_normalize(lines_read: str) -> tuple[str, list[str]]:
    """Normalize lines_read string and split into parts.

    Args:
        lines_read: String to normalize.

    Returns:
        tuple[str, list[str]]: (normalized_string, parts_list)
    """
    normalized = "".join(lines_read.split()).lower()

    if not normalized:
        return "", []

    return normalized, normalized.split(",")


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

    for raw_part in parts:
        part = raw_part.strip()
        if not part:
            continue

        if part == "full":
            has_full = True
            continue

        is_valid_range, is_invalid_part_flag = _process_validation_part(part)
        if is_valid_range:
            has_valid_range = True
        if is_invalid_part_flag:
            has_invalid_part = True

    return has_full, has_valid_range, has_invalid_part


def _validate_lines_read_decision(decision: ValidationDecision) -> None:
    """Make final validation decision.

    Args:
        decision: ValidationDecision object containing validation parameters.

    Raises:
        ValueError: If lines_read is invalid.
    """
    if decision.has_full:
        return

    if decision.has_invalid_part and not decision.has_valid_range and decision.normalized:
        error_msg = f"Invalid lines_read '{decision.lines_read}': no valid line ranges found"
        raise ValueError(error_msg)

    if not decision.has_valid_range and decision.normalized:
        error_msg = f"Invalid lines_read '{decision.lines_read}': no valid line ranges found"
        raise ValueError(error_msg)


def _validate_lines_read(lines_read: str | None) -> None:
    """Validate lines_read string format.

    Args:
        lines_read: String describing which lines were read, or None.
            None and empty string are valid (means no lines read).

    Raises:
        ValueError: If lines_read is invalid (e.g., no valid parts found)
    """
    if not lines_read:
        return

    normalized, parts = _validate_lines_read_normalize(lines_read)

    if not normalized:
        return  # Whitespace-only is valid "no lines read"

    has_full, has_valid_range, has_invalid_part = _validate_lines_read_process_parts(parts)

    decision = ValidationDecision(
        lines_read=lines_read,
        normalized=normalized,
        has_full=has_full,
        has_valid_range=has_valid_range,
        has_invalid_part=has_invalid_part,
    )
    _validate_lines_read_decision(decision)


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

    def __post_init__(self: WorkingMemoryEntry) -> None:
        """Validate fields after initialization.

        Note: lines_read may be None during deserialization, which is handled
        gracefully by _parse_line_ranges.
        """
        if self.lines_read is not None and not isinstance(self.lines_read, str):
            message = _type_error_message("lines_read", "a string or None", self.lines_read)
            raise TypeError(message)

        # Validate lines_read content if it's a string
        if isinstance(self.lines_read, str):
            _validate_lines_read(self.lines_read)

        # Validate key_insights is a list (or None)
        if self.key_insights is not None and not isinstance(self.key_insights, list):
            message = _type_error_message("key_insights", "a list or None", self.key_insights)
            raise TypeError(message)

    def with_normalized_path(self: WorkingMemoryEntry) -> WorkingMemoryEntry:
        """Return a copy of this entry with path normalized and insights defensively copied.

        Returns:
            WorkingMemoryEntry: A new entry with a normalized path and copied insights.
        """
        return replace(
            self,
            path=_normalize_path(self.path),
            key_insights=_copy_insights(self.key_insights),
        )

    # Expose module-level validators as static methods for backward compatibility.
    _validate_range_part = staticmethod(_validate_range_part)
    _validate_single_line_part = staticmethod(_validate_single_line_part)
    _process_validation_part = staticmethod(_process_validation_part)
    _validate_lines_read_normalize = staticmethod(_validate_lines_read_normalize)
    _validate_lines_read_process_parts = staticmethod(_validate_lines_read_process_parts)
    _validate_lines_read_decision = staticmethod(_validate_lines_read_decision)
    _validate_lines_read = staticmethod(_validate_lines_read)


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

    def update_from(self: ProblemEntry, updated: ProblemEntry) -> None:
        """Apply status and resolution from another problem entry.
        
        Args:
            updated: Another ProblemEntry instance containing updated status
                     and resolution values to apply to this entry.
        
        Returns:
            None
        """
        self.status = updated.status
        self.resolution = updated.resolution

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
        self.recent_files.append(entry.with_normalized_path())

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
        self.problems_encountered.append(_require_problem_entry(entry, "entry"))

    def update_problem(self: WorkingMemory, updated: ProblemEntry) -> None:
        """Update an existing problem entry.
        Args:
            updated: The updated problem entry containing new status and resolution.

        Returns:
            None

        Raises:
            ValueError: If no problem with matching description is found.
        """
        updated_entry = _require_problem_entry(updated, "updated")
        problem_name = updated_entry.problem

        for problem in self.problems_encountered:
            if problem.problem == problem_name:
                problem.update_from(updated_entry)
                break
        else:
            message = f"Problem '{problem_name}' not found"
            raise ValueError(message)

    def _get_empty_ranges_reason(
        self: WorkingMemory,
        state: EmptyRangesState,
    ) -> str:
        """Get appropriate reason when valid_ranges is empty.

        Args:
            state: Metadata about whether prior entries were empty or invalid.

        Returns:
            Reason string.
        """
        if state.all_lines_read_empty:
            return "No lines have been read"
        if state.any_lines_read_invalid:
            return "Cannot determine - invalid lines_read format"
        # Should not happen, but handle gracefully
        return "Cannot determine - no valid line ranges"

    def should_read_file(
        self: WorkingMemory,
        path: PathInput,
        start: int | None = None,
        end: int | None = None,
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
        is_invalid, reason, normalized_start, normalized_end = _validate_and_normalize_line_numbers(
            start,
            end,
        )
        if is_invalid:
            return True, reason
        start, end = normalized_start, normalized_end
        normalized_path = _normalize_path(path)
        matches = [e for e in reversed(self.recent_files) if e.path == normalized_path]
        if not matches:
            return True, "File not in recent files"
        _, all_empty, any_invalid = _collect_valid_ranges_from_matches(matches)
        empty_ranges_state = EmptyRangesState(
            all_lines_read_empty=all_empty,
            any_lines_read_invalid=any_invalid,
        )
        return FileReadDecisionMaker.should_read_file(
            matches=matches,
            start=start,
            end=end,
            get_empty_ranges_reason=lambda: self._get_empty_ranges_reason(empty_ranges_state),
        )

    def get_file_insights(self: WorkingMemory, path: PathInput) -> list[str]:
        """Return cached insights for a file.

        Args:
            path: The file path to retrieve insights for.

        Returns:
            A list of string insights previously recorded for the file.
        """
        normalized_path = _normalize_path(path)
        return [
            insight
            for entry in self.recent_files
            if entry.path == normalized_path
            for insight in entry.key_insights
        ]

    def update_after_read(
        self: WorkingMemory,
        path: PathInput,
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

    def prune_recent_files(
        self: WorkingMemory,
        max_entries: int = MAX_RECENT_FILES_DEFAULT,
    ) -> None:
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

    def create_memory(
        self: WorkingMemorySystem,
        task: str,
        objectives: list[str] | None = None,
    ) -> str:
        """Create a new working memory.

        Args:
            task: A string describing the current task.
            objectives: Optional list of specific objectives for the task.
                Defaults to an empty list.

        Returns:
            str: The unique task ID (UUID) assigned to the new memory.
        """
        task_id = str(uuid.uuid4())
        self.memories[task_id] = WorkingMemory(
            current_task=task,
            task_objectives=objectives or [],
        )
        self.current_task_id = task_id
        return task_id

    def switch_memory(self: WorkingMemorySystem, task_id: str) -> None:
        """Switch active memory.

        Args:
            task_id: The task ID to switch to.

        Raises:
            KeyError: If the task ID is not found in the memory registry.

        Returns:
            None: This method does not return a value.
        """
        if task_id not in self.memories:
            message = f"Task ID '{task_id}' not found"
            raise KeyError(message)
        self.current_task_id = task_id

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
            message = "No current task to archive"
            raise ValueError(message)

        mem = self.memories[self.current_task_id]
        path = archive_dir / f"working_memory_{self.current_task_id}.yaml"
        mem.save(path)
        del self.memories[self.current_task_id]
        self.current_task_id = None
        return path
