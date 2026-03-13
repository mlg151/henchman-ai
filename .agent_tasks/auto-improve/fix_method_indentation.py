"""Fix method indentation in intelligent_context.py."""

# Read the file
with open('src/henchman/utils/intelligent_context.py', 'r') as f:
    lines = f.readlines()

# Find where ContentExtractor class starts
content_extractor_start = -1
for i, line in enumerate(lines):
    if line.strip() == 'class ContentExtractor:':
        content_extractor_start = i
        break

if content_extractor_start == -1:
    print("Error: Could not find ContentExtractor class")
    exit(1)

# Find where the next class starts (or end of file)
next_class_start = len(lines)
for i in range(content_extractor_start + 1, len(lines)):
    if lines[i].strip().startswith('class ') and 'ContentExtractor' not in lines[i]:
        next_class_start = i
        break

print(f"ContentExtractor class from line {content_extractor_start} to {next_class_start}")

# Fix indentation for methods in this range
fixed_lines = []
for i, line in enumerate(lines):
    if content_extractor_start < i < next_class_start:
        # Lines inside ContentExtractor class
        if line.startswith('    @') or line.startswith('    def '):
            # Method decorator or definition, should have 8 spaces total
            # Currently has 4, so add 4 more
            fixed_lines.append('    ' + line)
        elif line.strip() and not line.startswith('        '):
            # Other non-empty line that doesn't start with 8 spaces
            # Might be class variable or method body
            # Check if previous line was a method definition
            if i > 0 and ('def ' in lines[i-1] or '@' in lines[i-1]):
                # Method body, should have 8 spaces
                fixed_lines.append('    ' + line)
            else:
                # Keep as is
                fixed_lines.append(line)
        else:
            # Already has correct indentation or empty line
            fixed_lines.append(line)
    else:
        # Outside ContentExtractor class
        fixed_lines.append(line)

# Write back
with open('src/henchman/utils/intelligent_context.py', 'w') as f:
    f.writelines(fixed_lines)

print("Fixed method indentation")