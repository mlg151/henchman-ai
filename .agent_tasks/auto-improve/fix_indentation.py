"""Fix indentation for ContentExtractor class methods."""

import re

def fix_content_extractor_indentation(content: str) -> str:
    """Fix indentation for ContentExtractor class methods.
    
    The issue is that methods after ContentExtractor._create_extractor_methods()
    are at module level but should be inside the class.
    """
    lines = content.split('\n')
    in_content_extractor = False
    fixed_lines = []
    
    for i, line in enumerate(lines):
        # Check if we're entering ContentExtractor class
        if line.strip() == 'class ContentExtractor:':
            in_content_extractor = True
            fixed_lines.append(line)
            continue
        
        # Check if we're at the ContentExtractor._create_extractor_methods() call
        if line.strip() == 'ContentExtractor._create_extractor_methods()':
            # This should be inside the class, so add 4 spaces
            fixed_lines.append('    ' + line)
            continue
        
        # Check if we're at a method that should be inside the class
        # Methods start with 4 spaces and @staticmethod or def
        if (in_content_extractor and 
            line.startswith('    @') and 
            ('@staticmethod' in line or '@classmethod' in line)):
            # This method should be inside the class, so it needs 8 spaces total
            # But it already has 4, so add 4 more
            fixed_lines.append('    ' + line)
            continue
        
        # Check for method definitions
        if (in_content_extractor and 
            line.startswith('    def ') and 
            i > 0 and lines[i-1].strip() != '@staticmethod' and lines[i-1].strip() != '@classmethod'):
            # Regular method definition, needs 8 spaces total
            fixed_lines.append('    ' + line)
            continue
        
        # Check for other lines inside class (already indented with 4 spaces)
        if in_content_extractor and line.startswith('    ') and not line.startswith('        '):
            # This line is inside the class but not a method, add 4 more spaces
            fixed_lines.append('    ' + line)
            continue
        
        # Check if we're leaving ContentExtractor class
        if in_content_extractor and line.strip() and not line.startswith('    '):
            # This line is not indented, so we're leaving the class
            in_content_extractor = False
        
        # Add line as-is
        fixed_lines.append(line)
    
    return '\n'.join(fixed_lines)

# Read the file
with open('src/henchman/utils/intelligent_context.py', 'r') as f:
    content = f.read()

# Fix the indentation
fixed_content = fix_content_extractor_indentation(content)

# Write back
with open('src/henchman/utils/intelligent_context.py', 'w') as f:
    f.write(fixed_content)

print("Fixed indentation for ContentExtractor class")