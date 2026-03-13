"""Fix the single indentation issue at line 172."""

# Read the file
with open('src/henchman/utils/intelligent_context.py', 'r') as f:
    lines = f.readlines()

# The issue is at line 172 (0-indexed: 171)
# Line 170: ContentExtractor._create_extractor_methods()
# Line 171: (empty)
# Line 172: @staticmethod

# We need to move ContentExtractor._create_extractor_methods() to the end of ContentExtractor class
# First, find where ContentExtractor class ends
content_extractor_end = -1
for i in range(170, len(lines)):
    if lines[i].strip().startswith('class ') and 'ContentExtractor' not in lines[i]:
        content_extractor_end = i
        break

if content_extractor_end == -1:
    # If not found, use end of file
    content_extractor_end = len(lines)

print(f"ContentExtractor class ends around line {content_extractor_end}")

# Remove the ContentExtractor._create_extractor_methods() line from its current position
# and insert it at the end of ContentExtractor class
new_lines = []
method_call_line = None
method_call_line_num = -1

for i, line in enumerate(lines):
    if 'ContentExtractor._create_extractor_methods()' in line:
        method_call_line = line
        method_call_line_num = i
        # Don't add this line now, we'll add it later
        continue
    
    new_lines.append(line)
    
    # If we've reached the end of ContentExtractor class, insert the method call
    if i == content_extractor_end - 1 and method_call_line:
        new_lines.append('\n')
        new_lines.append(method_call_line)

# If we never found where to insert it, add at the end
if method_call_line and method_call_line_num == -1:
    new_lines.append('\n')
    new_lines.append(method_call_line)

# Write back
with open('src/henchman/utils/intelligent_context.py', 'w') as f:
    f.writelines(new_lines)

print("Fixed the indentation issue")