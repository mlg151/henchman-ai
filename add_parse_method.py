#!/usr/bin/env python3
import sys

with open('src/henchman/agents/working_memory.py', 'r') as f:
    lines = f.readlines()

# Find the end of _merge_ranges method
insert_at = None
in_method = False
for i, line in enumerate(lines):
    if '@staticmethod' in line and 'def _merge_ranges' in lines[i+1]:
        in_method = True
    if in_method and line.strip() == 'return merged':
        # Found the return statement, insert after the next blank line
        for j in range(i+1, len(lines)):
            if lines[j].strip() == '':
                insert_at = j + 1
                break
        if insert_at is None:
            insert_at = i + 2  # After return and the line after
        break

if insert_at is not None:
    new_method = '''    @staticmethod
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
        """
        if not lines_read or not isinstance(lines_read, str):
            return []
        
        # Normalize: remove whitespace, convert to lowercase
        normalized = "".join(lines_read.split()).lower()
        if normalized == "full":
            return []
        
        ranges = []
        for part in normalized.split(","):
            if "-" in part:
                try:
                    start_str, end_str = part.split("-", 1)
                    start = int(start_str)
                    end = int(end_str)
                    if start < 1 or end < 1:
                        continue  # Skip invalid
                    if start > end:
                        continue  # Skip invalid
                    ranges.append(LineRange(start, end))
                except (ValueError, TypeError):
                    continue  # Skip invalid
            else:
                # Single line
                try:
                    line = int(part)
                    if line < 1:
                        continue
                    ranges.append(LineRange(line, line))
                except (ValueError, TypeError):
                    continue
        
        return ranges

'''
    lines.insert(insert_at, new_method)
    
    with open('src/henchman/agents/working_memory.py', 'w') as f:
        f.writelines(lines)
    print(f"Method added at line {insert_at}")
else:
    print("Could not find insertion point")
    sys.exit(1)