"""Test for bug with 'full' in _parse_line_ranges."""

from henchman.agents.working_memory import WorkingMemory, WorkingMemoryEntry

def test_full_bug():
    """Test that _parse_line_ranges("full") returns empty list, causing issues.
    
    When file was read "full" in older entry and partially in newer entry,
    the "full" doesn't contribute to valid_ranges, so we might re-read lines
    that were actually read in the full read.
    """
    memory = WorkingMemory(current_task="Test")
    
    # Older: full read
    memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "Full read", "full"))
    # Newer: partial read
    memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "Partial read", "10-50"))
    
    # Check _parse_line_ranges behavior
    ranges_full = memory._parse_line_ranges("full")
    print(f"_parse_line_ranges('full') = {ranges_full}")  # []
    
    ranges_partial = memory._parse_line_ranges("10-50")
    print(f"_parse_line_ranges('10-50') = {ranges_partial}")  # [LineRange(10,50)]
    
    # Request lines 60-80 (were read in full read but not in partial)
    should_read, reason = memory.should_read_file("/test/file.py", 60, 80)
    print(f"should_read: {should_read}, reason: {reason}")
    
    # Current behavior: returns True (should read)
    # Because most recent is partial (10-50), not "full"
    # valid_ranges = [LineRange(10,50)] (full returns [])
    # 60-80 not in valid_ranges
    
    # Is this a bug? File WAS read fully before!
    # The full read should count for something.
    
    # Actually, maybe it's by design. The partial read might indicate
    # the file changed, or we're focusing on specific lines.
    
    # But what if partial read is SUBSET of full read?
    # Example: read fully, then read lines 10-50 (to check them).
    # Lines 60-80 were still read in the full read!
    
    print("\nThis demonstrates the design choice: older full reads are ignored when newer partial reads exist.")
    print("Whether this is a bug depends on the intended semantics.")

if __name__ == "__main__":
    test_full_bug()