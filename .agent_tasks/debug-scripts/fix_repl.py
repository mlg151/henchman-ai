import sys

with open("src/henchman/cli/repl.py") as f:
    lines = f.readlines()

# Find the _handle_tool_call method
in_method = False
method_start = -1
for i, line in enumerate(lines):
    if "async def _handle_tool_call" in line:
        in_method = True
        method_start = i
    elif in_method and line.strip() and not line.startswith(" ") and not line.startswith("\t"):
        # Found the end of the method
        method_end = i
        break

if method_start == -1:
    print("Could not find _handle_tool_call method")
    sys.exit(1)

# Find the lines to replace (lines starting at "# Submit result to agent")
for i in range(method_start, method_end):
    if "# Submit result to agent" in lines[i]:
        submit_start = i
        # Find the end of this block (look for next line that's not part of the continuation)
        for j in range(i, method_end):
            if lines[j].strip() and not lines[j].startswith(" ") and not lines[j].startswith("\t"):
                # Found a line that's not indented - end of block
                submit_end = j
                break
        else:
            submit_end = method_end
        break

# Replace the block
new_block = """        # Only submit result and continue execution if tool was successful
        if result.success:
            # Submit result to agent
            self.agent.submit_tool_result(tool_call.id, result.content)

            # Continue agent execution with tool results
            async for event in self.agent.continue_with_tool_results():
                await self._handle_agent_event(event)
        else:
            # Tool failed, don't submit result or continue execution
            # The agent will remain in its current state
            pass
"""

# Replace the lines
lines[submit_start:submit_end] = [new_block]

# Write back
with open("src/henchman/cli/repl.py", "w") as f:
    f.writelines(lines)

print("Fixed _handle_tool_call method")
