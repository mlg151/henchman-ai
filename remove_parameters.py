import re
import os

file_path = '/home/matthew/mlg-cli/tests/utils/test_summarization.py'
with open(file_path, 'r') as f:
    content = f.read()

# Pattern to match compact_with_summarization(...)
# It handles multiline calls
pattern = r'await compact_with_summarization\((.*?)\)'

def replace_call(match):
    args_str = match.group(1).strip()
    # Check if it's already using keyword arguments mostly
    # We want to transform:
    # await compact_with_summarization(msgs, max_tokens=100, provider=mock_provider, summarize=True)
    # into:
    # await compact_messages(CompactionParams(messages=msgs, max_tokens=100, provider=mock_provider, summarize=True))
    
    # Simple heuristic: split by comma but be careful about nested parens/brackets
    # Actually, we can just wrap the whole thing in CompactionParams and rename the function
    
    # If the first argument doesn't have '=', it's 'messages'
    # If the second argument doesn't have '=', it's 'max_tokens'
    
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

new_content = re.sub(pattern, replace_call, content, flags=re.DOTALL)

with open(file_path, 'w') as f:
    f.write(new_content)
