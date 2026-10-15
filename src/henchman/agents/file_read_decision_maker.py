"""File read decision maker for WorkingMemory."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

    from henchman.agents.working_memory import WorkingMemoryEntry

from henchman.agents.line_range_utils import (
    LineRange,
    merge_line_ranges,
    parse_line_ranges,
)

# ---------------------------------------------------------------------------
# Module-level helpers (no class state needed)
# ---------------------------------------------------------------------------


def _validate_line_number(
    value: int | None, param_name: str,
) -> tuple[bool, str]:
    """Validate a single line number parameter.

    Args:
        value: The line number value to validate.
        param_name: Parameter name ('start' or 'end').

    Returns:
        tuple[bool, str]: (is_invalid, error_message)
    """
    if value is None:
        return False, ""  # None is valid

    # Reject boolean values (bool is a subclass of int in Python)
    if isinstance(value, bool):
        type_name = type(value).__name__
        return True, (
            f"Invalid line number: {param_name} must be an integer, "
            f"got {type_name}={value}"
        )

    if not isinstance(value, int):
        type_name = type(value).__name__
        return True, (
            f"Invalid line number: {param_name} must be an integer, "
            f"got {type_name}={value}"
        )

    # end=-1 is allowed (means "read to EOF"), other negative values are not
    if param_name == "end" and value == -1:
        return False, ""  # -1 is valid for end

    if value < 1:
        return True, (
            f"Invalid line number: {param_name} must be positive "
            f"(1-indexed), got {param_name}={value}"
        )

    return False, ""


def _validate_and_normalize_line_numbers(
    start: int | None, end: int | None,
) -> tuple[bool, str, int | None, int | None]:
    """Validate line numbers and normalize special values.

    Args:
        start: Optional starting line number (1-indexed).
        end: Optional ending line number (inclusive) or -1 for EOF.

    Returns:
        tuple[bool, str, int | None, int | None]: A tuple where:
            - First element: True if validation failed, False otherwise
            - Second element: Error message if validation failed, empty string otherwise
            - Third element: Normalized start value (None if input was None)
            - Fourth element: Normalized end value (None if input was None or -1)
    """
    start_invalid, start_error = _validate_line_number(start, "start")
    if start_invalid:
        return True, start_error, start, end

    end_invalid, end_error = _validate_line_number(end, "end")
    if end_invalid:
        return True, end_error, start, end

    # Convert end=-1 to None (read to end of file)
    normalized_end = None if end == -1 else end

    # Validate line range if both are provided (and end is not -1)
    if start is not None and end is not None and end != -1 and start > end:
        return True, (
            f"Invalid line range: start ({start}) > end ({end}) - "
            "line numbers must be in ascending order"
        ), start, end

    return False, "", start, normalized_end


def _get_full_read_reason(matches: list[WorkingMemoryEntry]) -> str | None:
    """Check if any entry indicates the file was read fully.

    Args:
        matches: List of WorkingMemoryEntry objects for the file.

    Returns:
        str: Reason string if file was read fully, None otherwise.
    """
    for entry in matches:
        if entry.lines_read:
            parts = [part.strip().lower() for part in entry.lines_read.split(",")]
            if "full" in parts:
                return "File already read (full)"
    return None


def _collect_valid_ranges_from_matches(
    matches: list[WorkingMemoryEntry],
) -> tuple[list[LineRange], bool, bool]:
    """Collect valid line ranges from matches and track metadata.

    Args:
        matches: List of WorkingMemoryEntry objects.

    Returns:
        tuple[list[LineRange], bool, bool]: A tuple containing:
            - List of valid LineRange objects
            - Boolean indicating if all entries have empty lines_read
            - Boolean indicating if any entry has invalid lines_read format
    """
    valid_ranges: list[LineRange] = []
    all_lines_read_empty = True
    any_lines_read_invalid = False

    for match in matches:
        lines_read = match.lines_read
        if not lines_read:
            continue

        all_lines_read_empty = False
        try:
            ranges = parse_line_ranges(lines_read)
            valid_ranges.extend(ranges)
        except ValueError:
            any_lines_read_invalid = True

    return valid_ranges, all_lines_read_empty, any_lines_read_invalid


def _handle_partial_range_specification(
    start: int | None,
    end: int | None,
    valid_ranges: list[LineRange],
    get_empty_ranges_reason: Callable[[], str],
) -> tuple[bool, str]:
    """Handle partial range specifications (when start or end is None).

    Args:
        start: Optional starting line number.
        end: Optional ending line number.
        valid_ranges: List of valid LineRange objects from previous reads.
        get_empty_ranges_reason: Function that returns reason when no valid ranges.

    Returns:
        tuple[bool, str]: Whether to read and reason.
    """
    if not valid_ranges:
        return True, get_empty_ranges_reason()

    if start is None and end is not None:
        min_start = min((rng.start for rng in valid_ranges), default=float("inf"))
        if end < min_start:
            return True, f"End line {end} before first read line {min_start}"
        return True, f"May need to read lines before {min_start}"

    if end is None and start is not None:
        max_end = max((rng.end for rng in valid_ranges), default=0)
        if start > max_end:
            return True, f"Start line {start} beyond last read line {max_end}"
        return True, f"May need to read lines beyond {max_end}"

    # Both are None — file was only partially read (full-read case exits earlier)
    return True, "File has been partially read, whole file not read"


def _is_range_covered(requested: LineRange, merged_ranges: list[LineRange]) -> bool:
    """Return True if *requested* is fully spanned by *merged_ranges*.

    Args:
        requested: The line range the caller wants to read.
        merged_ranges: Already-merged list of previously read ranges.

    Returns:
        True when the requested range is fully covered, False otherwise.
    """
    current_line = requested.start
    for rng in merged_ranges:
        if current_line < rng.start:
            return False  # gap before this range
        if current_line <= rng.end:
            current_line = rng.end + 1
            if current_line > requested.end:
                return True  # entire requested range covered
    return False


def _check_full_range_coverage(
    start: int,
    end: int,
    valid_ranges: list[LineRange],
    get_empty_ranges_reason: Callable[[], str],
) -> tuple[bool, str]:
    """Check if a requested line range is fully covered by previous reads.

    Args:
        start: Starting line number (1-indexed).
        end: Ending line number (inclusive).
        valid_ranges: List of valid LineRange objects from previous reads.
        get_empty_ranges_reason: Function that returns reason when no valid ranges.

    Returns:
        tuple[bool, str]: Whether to read and reason.
    """
    if not valid_ranges:
        return True, get_empty_ranges_reason()

    merged_ranges = merge_line_ranges(valid_ranges)
    requested = LineRange(start, end)

    if _is_range_covered(requested, merged_ranges):
        return False, "File already read (covered)"
    return True, "New or partially overlapping lines need to be read"


# ---------------------------------------------------------------------------
# Public API — thin class wrapper that delegates to module-level helpers
# ---------------------------------------------------------------------------


class FileReadDecisionMaker:
    """Makes decisions about whether files need to be read based on history."""

    # Expose module-level helpers as static methods for backward compatibility
    _validate_line_number = staticmethod(_validate_line_number)
    _validate_and_normalize_line_numbers = staticmethod(_validate_and_normalize_line_numbers)
    _get_full_read_reason = staticmethod(_get_full_read_reason)
    _collect_valid_ranges_from_matches = staticmethod(_collect_valid_ranges_from_matches)
    _handle_partial_range_specification = staticmethod(_handle_partial_range_specification)
    _check_full_range_coverage = staticmethod(_check_full_range_coverage)

    @staticmethod
    def should_read_file(
        matches: list[WorkingMemoryEntry],
        start: int | None,
        end: int | None,
        get_empty_ranges_reason: Callable[[], str],
    ) -> tuple[bool, str]:
        """Determine whether a file needs to be read based on matches.

        Args:
            matches: List of WorkingMemoryEntry objects for the file.
            start: Optional starting line number (1-indexed) for the read range.
            end: Optional ending line number (inclusive) for the read range.
            get_empty_ranges_reason: Function that returns reason when no valid ranges.

        Returns:
            tuple[bool, str]: (should_read, reason)
        """
        full_read_reason = _get_full_read_reason(matches)
        if full_read_reason is not None:
            return False, full_read_reason

        valid_ranges, all_lines_read_empty, any_lines_read_invalid = (
            _collect_valid_ranges_from_matches(matches)
        )

        def _empty_reason() -> str:
            if all_lines_read_empty:
                return "No lines have been read"
            if any_lines_read_invalid:
                return "Cannot determine - invalid lines_read format"
            return "Cannot determine - no valid line ranges"

        empty_reason_func = get_empty_ranges_reason

        if start is None or end is None:
            return _handle_partial_range_specification(
                start, end, valid_ranges, empty_reason_func,
            )

        return _check_full_range_coverage(start, end, valid_ranges, empty_reason_func)
