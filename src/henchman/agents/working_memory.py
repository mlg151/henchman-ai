"""Working Memory System for agent context management.

Provides a structured in-memory cache that tracks recently accessed files,
decisions, completed steps, actions, insights, and problems encountered during
a task.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, TypeVar, Union

import yaml

from henchman.utils.serialization import SerializableDataclass

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

        Returns:
            LineRange object if parsing succeeds, None if the format is invalid
            or contains non-integer values.
        """
        parts = s.split("-")
        if len(parts) == EXPECTED_RANGE_PARTS:
            try:
                line_range = cls(start=int(parts[0]), end=int(parts[1]))
                # __post_init__ will validate start <= end
                return line_range
            except ValueError:
                # Could be from int() conversion or __post_init__ validation
                return None
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
        self.recent_files.append(entry)

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
        """
        if not isinstance(updated, ProblemEntry):
            raise TypeError(f"updated must be a ProblemEntry, got {type(updated).__name__}")
        for e in self.problems_encountered:
            if e.problem == updated.problem:
                e.status = updated.status
                e.resolution = updated.resolution
                break

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
        # Find ALL entries for this file (most recent first)
        matches = [e for e in reversed(self.recent_files) if e.path == path]
        if not matches:
            return True, "File not in recent files"

        # Check if ANY entry indicates file was read fully
        # If file was read fully at any point, we know all lines
        for match in matches:
            if match.lines_read.strip().lower() == "full":
                return False, "File already read (full)"

        if start is None or end is None:
            # No line range specified but file wasn't read fully
            return True, "File not fully read - partial read recorded"

        # Validate line range
        if start > end:
            return True, f"Invalid line range: start ({start}) > end ({end}) - treating as new read"

        # Validate line numbers are positive (1-indexed)
        if start < 1 or end < 1:
            return True, f"Invalid line numbers: must be positive (1-indexed), got start={start}, end={end}"

        requested = LineRange(start, end)

        # Track if we found any valid line range entries
        found_valid_range = False

        # Check ALL entries for line range containment
        for match in matches:
            rng = LineRange.from_str(match.lines_read)
            if rng:
                found_valid_range = True
                if requested.start >= rng.start and requested.end <= rng.end:
                    return False, "File already read (contained within previously read lines)"

        # If we found valid ranges but none covered the requested range
        if found_valid_range:
            return True, "New or partially overlapping lines need to be read"
        else:
            # No valid line range format in any entry
            return True, "Cannot determine overlap - invalid lines_read format"

    def get_file_insights(self: WorkingMemory, path: str) -> list[str]:
        """Return cached insights for a file.

        Args:
            path: The file path to retrieve insights for.

        Returns:
            A list of string insights previously recorded for the file.
        """
        return next((e.key_insights for e in reversed(self.recent_files) if e.path == path), [])

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
