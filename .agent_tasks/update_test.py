#!/usr/bin/env python3
"""Update test file to fix session manager references."""

import re

with open('tests/cli/test_repl.py', 'r') as f:
    content = f.read()

# Pattern to match the specific lines in test_session_messages_recorded_during_conversation
# We need to be careful to only update the right test
lines = content.split('\n')
updated_lines = []

i = 0
while i < len(lines):
    line = lines[i]
    # Look for the test_session_messages_recorded_during_conversation test
    if 'def test_session_messages_recorded_during_conversation' in line:
        # Find the repl.session_manager assignment in this test
        j = i
        while j < len(lines):
            if 'repl.session_manager = ReplSessionManager' in lines[j] and 'auto_save=True' in lines[j]:
                # Found it, update this and the next few lines
                updated_lines.append('        repl = Repl(provider=provider, console=console, config=config)')
                updated_lines.append('        # Replace session manager in all components')
                updated_lines.append('        new_session_manager = ReplSessionManager(session_manager=manager, auto_save=True)')
                updated_lines.append('        repl.session_manager = new_session_manager')
                updated_lines.append('        repl.output_handler.session_manager = new_session_manager')
                updated_lines.append('        # ToolExecutor uses output_handler.session_manager')
                updated_lines.append('        session = manager.create_session(project_hash="test-project")')
                updated_lines.append('        repl.set_session(session)')
                # Skip the original lines we're replacing
                # Skip: repl = Repl(provider=provider, console=console, config=config)
                # Skip: repl.session_manager = ReplSessionManager(session_manager=manager, auto_save=True)
                # Skip: session = manager.create_session(project_hash="test-project")
                # Skip: repl.set_session(session)
                # We already skipped the first line (repl = Repl...)
                # Now skip the next 3 lines
                i += 3  # We'll increment i by 1 at the end of loop, so skip 3 more
                j += 3  # Skip in inner loop
                # Find where to continue
                while j < len(lines) and not lines[j].strip().startswith('#'):
                    j += 1
                i = j - 1  # Adjust i to continue from here
                break
            j += 1
    else:
        updated_lines.append(line)
    i += 1

with open('tests/cli/test_repl.py', 'w') as f:
    f.write('\n'.join(updated_lines))

print("Updated test file")