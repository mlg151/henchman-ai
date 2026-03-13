import re
import os

files = [
    '/home/matthew/mlg-cli/tests/utils/test_compaction_validation.py',
    '/home/matthew/mlg-cli/tests/utils/test_coverage_boost.py',
    '/home/matthew/mlg-cli/tests/utils/test_missing_coverage.py',
    '/home/matthew/mlg-cli/tests/core/test_missing_coverage.py',
]

pattern = r'await compact_with_summarization\((.*?)\)'

def replace_call(match):
    args_str = match.group(1).strip()
    args = []
    current_arg = ""
    bracket_level = 0
    paren_level = 0
    for char in args_str:
        if char == ',' and bracket_level == 0 and paren_level == 0:
            args.append(current_arg.strip())
            current_arg = ""
        else:
            current_arg += char
            if char in '([{':
                bracket_level += 1
            elif char in ')]}':
                bracket_level -= 1
    if current_arg:
        args.append(current_arg.strip())
        
    new_args = []
    for i, arg in enumerate(args):
        if i == 0 and '=' not in arg:
            new_args.append(f"messages={arg}")
        elif i == 1 and '=' not in arg:
            new_args.append(f"max_tokens={arg}")
        else:
            new_args.append(arg)
            
    return f"await compact_messages(CompactionParams({', '.join(new_args)}))"

for file_path in files:
    if not os.path.exists(file_path):
        print(f"File not found: {file_path}")
        continue
        
    with open(file_path, 'r') as f:
        content = f.read()

    # Update imports
    content = content.replace('compact_with_summarization', 'CompactionParams, compact_messages')
    # If it was imported from henchman.utils.compaction
    
    new_content = re.sub(pattern, replace_call, content, flags=re.DOTALL)

    with open(file_path, 'w') as f:
        f.write(new_content)
    print(f"Updated {file_path}")
