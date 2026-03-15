"""Test for the lines_read=None bug."""
import tempfile
from pathlib import Path
import yaml
from henchman.agents.working_memory import WorkingMemory, WorkingMemoryEntry

def test_lines_read_none():
    """Test that lines_read=None is handled correctly."""
    # Create a memory with an entry where lines_read=None
    memory = WorkingMemory(current_task="Test")
    
    # Manually create an entry with lines_read=None (simulating loading from YAML)
    # This is tricky because WorkingMemoryEntry has type hint str for lines_read
    # But Python won't enforce it at runtime
    entry_dict = {
        "path": "/test/file.py",
        "purpose": "Test",
        "lines_read": None,  # This could happen from YAML with lines_read: null
        "key_insights": [],
        "timestamp": "2024-01-01T00:00:00Z"
    }
    
    # Use from_dict to create entry (simulating load from YAML)
    entry = WorkingMemoryEntry.from_dict(entry_dict)
    print(f"Entry lines_read type: {type(entry.lines_read)}, value: {entry.lines_read}")
    
    memory.add_recent_file(entry)
    
    # Now test should_read_file
    # The file should be considered NOT fully read because lines_read is None
    # But actually, lines_read=None means "unknown what was read", not "nothing was read"
    # The current implementation will treat it as "not fully read"
    should_read, reason = memory.should_read_file("/test/file.py", 10, 50)
    print(f"should_read: {should_read}, reason: {reason}")
    
    # With the bug: should_read=True, reason="Cannot determine - invalid lines_read format"
    # Actually, that's probably correct behavior! lines_read=None is invalid.
    
    # But what if the file WAS marked as "full" but saved as null in YAML?
    # That's the bug: data loss/corruption leads to incorrect behavior.

def test_yaml_roundtrip():
    """Test YAML save/load with lines_read=None."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create memory with entry
        memory = WorkingMemory(current_task="Test")
        entry = WorkingMemoryEntry(
            path="/test/file.py",
            purpose="Test",
            lines_read="full",  # Marked as full
        )
        memory.add_recent_file(entry)
        
        # Save to YAML
        file_path = Path(tmpdir) / "memory.yaml"
        memory.save(file_path)
        
        # Manually modify YAML to set lines_read: null
        with open(file_path, 'r') as f:
            data = yaml.safe_load(f)
        
        # Set lines_read to null for the first entry
        if data.get('recent_files'):
            data['recent_files'][0]['lines_read'] = None
        
        # Save modified YAML
        with open(file_path, 'w') as f:
            yaml.dump(data, f, default_flow_style=False)
        
        # Load modified YAML
        loaded = WorkingMemory.load(file_path)
        
        # Check what happened
        if loaded.recent_files:
            loaded_entry = loaded.recent_files[0]
            print(f"Loaded entry lines_read type: {type(loaded_entry.lines_read)}, value: {loaded_entry.lines_read}")
            
            # Test should_read_file
            should_read, reason = loaded.should_read_file("/test/file.py", 10, 50)
            print(f"After loading with lines_read=None: should_read={should_read}, reason={reason}")
            # BUG: Should be False (file was marked full), but will be True

if __name__ == "__main__":
    print("Test 1: lines_read=None")
    test_lines_read_none()
    print("\nTest 2: YAML roundtrip with lines_read: null")
    test_yaml_roundtrip()