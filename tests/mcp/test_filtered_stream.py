"""Tests for FilteredStream class."""

import sys
from unittest.mock import MagicMock

from henchman.mcp.client import FilteredStream


class TestFilteredStream:
    """Tests for FilteredStream."""

    def test_verbose_mode_passes_through(self) -> None:
        """Test that verbose mode passes all messages through to stderr."""
        # Mock stderr to capture output
        mock_stderr = MagicMock()
        # Make the mock return the length of the string (like real write() does)
        mock_stderr.write.side_effect = lambda s: len(s)
        original_stderr = sys.stderr
        try:
            sys.stderr = mock_stderr
            stream = FilteredStream(verbose=True)

            # Write various log messages
            result = stream.write("INFO 2024-01-01 12:00:00,000 - Some info\n")
            result2 = stream.write("DEBUG: Debug message\n")
            result3 = stream.write("[INFO] Another info\n")
            result4 = stream.write("ERROR: Something went wrong\n")

            # All messages should be passed through to stderr
            assert mock_stderr.write.call_count == 4
            assert result == len("INFO 2024-01-01 12:00:00,000 - Some info\n")
            assert result2 == len("DEBUG: Debug message\n")
            assert result3 == len("[INFO] Another info\n")
            assert result4 == len("ERROR: Something went wrong\n")
        finally:
            sys.stderr = original_stderr

    def test_non_verbose_mode_filters_info_debug(self) -> None:
        """Test that non-verbose mode filters out INFO and DEBUG messages."""
        # Mock stderr to capture output
        mock_stderr = MagicMock()
        mock_stderr.write.side_effect = lambda s: len(s)
        original_stderr = sys.stderr
        try:
            sys.stderr = mock_stderr
            stream = FilteredStream(verbose=False)

            # Write various log messages
            result1 = stream.write("INFO 2024-01-01 12:00:00,000 - Some info\n")
            result2 = stream.write("DEBUG: Debug message\n")
            result3 = stream.write("[INFO] Another info\n")
            result4 = stream.write("ERROR: Something went wrong\n")
            result5 = stream.write("WARNING: Warning message\n")
            result6 = stream.write("Some regular output\n")

            # Only ERROR, WARNING, and regular output should pass through
            assert mock_stderr.write.call_count == 3  # ERROR, WARNING, regular

            # INFO/DEBUG messages should be filtered out (return length but not written)
            assert result1 == len("INFO 2024-01-01 12:00:00,000 - Some info\n")
            assert result2 == len("DEBUG: Debug message\n")
            assert result3 == len("[INFO] Another info\n")
            assert result4 == len("ERROR: Something went wrong\n")
            assert result5 == len("WARNING: Warning message\n")
            assert result6 == len("Some regular output\n")
        finally:
            sys.stderr = original_stderr

    def test_various_log_formats(self) -> None:
        """Test that various common log formats are filtered."""
        mock_stderr = MagicMock()
        mock_stderr.write.side_effect = lambda s: len(s)
        original_stderr = sys.stderr
        try:
            sys.stderr = mock_stderr
            stream = FilteredStream(verbose=False)

            # Test various log formats
            test_cases = [
                # (input, should_pass_through)
                ("INFO 2024-01-01 12:00:00,000 - message", False),
                ("INFO: message", False),
                ("[INFO] message", False),
                ("DEBUG 2024-01-01 12:00:00,000 - message", False),
                ("DEBUG: message", False),
                ("[DEBUG] message", False),
                ("ERROR: message", True),
                ("WARNING: message", True),
                ("CRITICAL: message", True),
                ("Some regular output", True),
                ("", False),  # Empty line
                ("   ", False),  # Whitespace only
                ("Processing complete", True),  # Regular output
            ]

            for input_text, should_pass in test_cases:
                mock_stderr.write.reset_mock()
                result = stream.write(input_text + "\n")
                if should_pass:
                    # Should have been written to stderr
                    mock_stderr.write.assert_called_once()
                else:
                    # Should not have been written (except for empty/whitespace)
                    if input_text.strip():
                        mock_stderr.write.assert_not_called()
                assert result == len(input_text + "\n")
        finally:
            sys.stderr = original_stderr

    def test_empty_and_whitespace(self) -> None:
        """Test handling of empty lines and whitespace."""
        mock_stderr = MagicMock()
        mock_stderr.write.side_effect = lambda s: len(s)
        original_stderr = sys.stderr
        try:
            sys.stderr = mock_stderr
            stream = FilteredStream(verbose=False)

            # Empty lines should not cause writes
            result1 = stream.write("")
            result2 = stream.write("\n")
            result3 = stream.write("   \n")
            result4 = stream.write("  INFO: message  \n")  # Should be filtered

            # No writes should have occurred (INFO is filtered)
            mock_stderr.write.assert_not_called()

            # But lengths should still be returned
            assert result1 == 0
            assert result2 == len("\n")
            assert result3 == len("   \n")
            assert result4 == len("  INFO: message  \n")
        finally:
            sys.stderr = original_stderr
