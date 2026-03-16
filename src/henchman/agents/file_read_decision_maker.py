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
    check_line_in_merged_ranges,
)


class FileReadDecisionMaker:
    """Makes decisions about whether files need to be read based on history."""
    
    @staticmethod
    def _validate_line_number(
        value: int | None, param_name: str
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
            return True, f"Invalid line number: {param_name} must be an integer, got {type(value).__name__}={value}"

        if not isinstance(value, int):
            return True, f"Invalid line number: {param_name} must be an integer, got {type(value).__name__}={value}"

        # end=-1 is allowed (means "read to EOF"), other negative values are not
        if param_name == "end" and value == -1:
            return False, ""  # -1 is valid for end

        if value < 1:
            return True, f"Invalid line number: {param_name} must be positive (1-indexed), got {param_name}={value}"

        return False, ""

    @staticmethod
    def _validate_and_normalize_line_numbers(
        start: int | None, end: int | None
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
        # Validate start parameter
        start_invalid, start_error = FileReadDecisionMaker._validate_line_number(start, "start")
        if start_invalid:
            return True, start_error, start, end

        # Validate end parameter
        end_invalid, end_error = FileReadDecisionMaker._validate_line_number(end, "end")
        if end_invalid:
            return True, end_error, start, end

        # Convert end=-1 to None (read to end of file)
        normalized_end = end
        if end == -1:
            normalized_end = None

        # Validate line range if both are provided (and end is not -1)
        if start is not None and end is not None and end != -1 and start > end:
            return True, f"Invalid line range: start ({start}) > end ({end}) - line numbers must be in ascending order", start, end

        return False, "", start, normalized_end

    @staticmethod
    def _get_full_read_reason(matches: list["WorkingMemoryEntry"]) -> str | None:
        """Check if any entry indicates the file was read fully.

        Args:
            matches: List of WorkingMemoryEntry objects for the file.

        Returns:
            str: Reason string if file was read fully (e.g., "File already read (full)"),
                None otherwise.
        """
        for entry in matches:
            if entry.lines_read:
                # Check if "full" appears as a separate word in lines_read
                # Split by comma and strip whitespace
                parts = [part.strip().lower() for part in entry.lines_read.split(",")]
                if "full" in parts:
                    return "File already read (full)"
        return None

    @staticmethod
    def _collect_valid_ranges_from_matches(
        matches: list["WorkingMemoryEntry"]
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
                continue  # Skip entries with no lines_read

            all_lines_read_empty = False

            try:
                ranges = parse_line_ranges(lines_read)
                valid_ranges.extend(ranges)
            except ValueError:
                any_lines_read_invalid = True

        return valid_ranges, all_lines_read_empty, any_lines_read_invalid

    @staticmethod
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
        # If we have no valid ranges, we need to read
        if not valid_ranges:
            return True, get_empty_ranges_reason()

        # If start is None but end is specified, we're asking "read from beginning to end"
        if start is None and end is not None:
            # Find the minimum start line we've read
            min_start = min((rng.start for rng in valid_ranges), default=float('inf'))
            if end < min_start:
                return True, f"End line {end} before first read line {min_start}"
            # Even if end is within or after our ranges, we don't know about beginning
            return True, f"May need to read lines before {min_start}"

        # If end is None but start is specified, we're asking "read from start to end of file"
        if end is None and start is not None:
            # Find the maximum end line we've read
            max_end = max((rng.end for rng in valid_ranges), default=0)
            if start > max_end:
                return True, f"Start line {start} beyond last read line {max_end}"
            # Even if start is within or before our ranges, we don't know file size
            return True, f"May need to read lines beyond {max_end}"

        # Both are None - we're asking about the whole file
        # If file was read fully, we would have returned earlier in should_read_file
        # So if we get here, file was only partially read or we don't know
        return True, "File has been partially read, whole file not read"

    @staticmethod
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
        requested = LineRange(start, end)

        if not valid_ranges:
            # No valid line range format in any entry
            # This happens when lines_read is invalid, empty, or contains only invalid ranges
            return True, get_empty_ranges_reason()

        # Merge overlapping or adjacent ranges
        merged_ranges = merge_line_ranges(valid_ranges)

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

    @staticmethod
    def should_read_file(
        matches: list["WorkingMemoryEntry"],
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
            tuple[bool, str]: A tuple where the first element is a boolean indicating
            whether the file should be read (True = read, False = skip), and the second
            element is a string explaining the reason for the decision.
        """
        # Check if any entry indicates file was read fully
        full_read_reason = FileReadDecisionMaker._get_full_read_reason(matches)
        if full_read_reason is not None:
            return False, full_read_reason

        # Collect all valid line ranges from all entries (needed for partial range checks)
        valid_ranges, all_lines_read_empty, any_lines_read_invalid = (
            FileReadDecisionMaker._collect_valid_ranges_from_matches(matches)
        )

        # Helper to get appropriate reason when valid_ranges is empty
        def get_empty_ranges_reason_wrapper() -> str:
            if all_lines_read_empty:
                return "No lines have been read"
            elif any_lines_read_invalid:
                return "Cannot determine - invalid lines_read format"
            else:
                # Should not happen, but handle gracefully
                return "Cannot determine - no valid line ranges"

        # Use provided function or wrapper
        empty_reason_func = get_empty_ranges_reason or get_empty_ranges_reason_wrapper

        # Handle partial range specifications
        if start is None or end is None:
            return FileReadDecisionMaker._handle_partial_range_specification(
                start, end, valid_ranges, empty_reason_func
            )
        
        return FileReadDecisionMaker._check_full_range_coverage(
            start, end, valid_ranges, empty_reason_func
        )