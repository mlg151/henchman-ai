"""Fix all indentation issues in intelligent_context.py."""

import re

def fix_indentation(content: str) -> str:
    """Fix indentation issues in the file."""
    lines = content.split('\n')
    fixed_lines = []
    
    # Track if we're inside ContentExtractor class
    in_content_extractor = False
    # Track the start line of ContentExtractor class
    content_extractor_start = -1
    
    for i, line in enumerate(lines):
        # Check for ContentExtractor class start
        if line.strip() == 'class ContentExtractor:':
            in_content_extractor = True
            content_extractor_start = i
            fixed_lines.append(line)
            continue
        
        # Check if we're leaving ContentExtractor class
        if in_content_extractor and i > content_extractor_start:
            # Check if we've hit the next class
            if line.strip().startswith('class ') and line.strip() != 'class ContentExtractor:':
                in_content_extractor = False
            # Check if we've hit the ConversationTypeDetector class (line ~409)
            elif 'class ConversationTypeDetector:' in line:
                in_content_extractor = False
        
        # Fix indentation for methods inside ContentExtractor
        if in_content_extractor and i > content_extractor_start:
            # Methods should have 8 spaces (4 for class + 4 for method)
            # But they currently have 4 spaces
            if line.startswith('    @') or line.startswith('    def '):
                # Add 4 more spaces
                fixed_lines.append('    ' + line)
                continue
            # Other lines inside class should keep their indentation
            # But if they have 4 spaces, they might need 8
            elif line.startswith('    ') and not line.startswith('        '):
                # This is tricky - could be a class-level variable or method body
                # Let's check context
                if i > 0 and ('def ' in lines[i-1] or '@' in lines[i-1]):
                    # Method body line, should have 8 spaces
                    fixed_lines.append('    ' + line)
                else:
                    # Might be a class variable, keep as is
                    fixed_lines.append(line)
                continue
        
        # Keep other lines as-is
        fixed_lines.append(line)
    
    return '\n'.join(fixed_lines)

# Read the file
with open('src/henchman/utils/intelligent_context.py', 'r') as f:
    content = f.read()

# Fix indentation
fixed_content = fix_indentation(content)

# Write back
with open('src/henchman/utils/intelligent_context.py', 'w') as f:
    f.write(fixed_content)

print("Fixed indentation issues")