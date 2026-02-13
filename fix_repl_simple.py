#!/usr/bin/env python3


def fix_repl_file(filename):
    with open(filename) as f:
        lines = f.readlines()

    new_lines = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.strip() == "# Submit result to agent":
            # Check if this is the block we want to replace
            if (
                i + 5 < len(lines)
                and "async for event in self.agent.continue_with_tool_results()" in lines[i + 4]
            ):
                # Found the block to replace
                new_lines.append(
                    "        # Only submit result and continue execution if tool was successful\n"
                )
                new_lines.append("        if result.success:\n")
                new_lines.append("            # Submit result to agent\n")
                new_lines.append(
                    "            self.agent.submit_tool_result(tool_call.id, result.content)\n"
                )
                new_lines.append("\n")
                new_lines.append("            # Continue agent execution with tool results\n")
                new_lines.append(
                    "            async for event in self.agent.continue_with_tool_results():\n"
                )
                new_lines.append("                await self._handle_agent_event(event)\n")
                new_lines.append("        else:\n")
                new_lines.append(
                    "            # Tool failed, don't submit result or continue execution\n"
                )
                new_lines.append("            # The agent will remain in its current state\n")
                new_lines.append("            pass\n")
                # Skip the original 6 lines
                i += 6
                continue
        new_lines.append(line)
        i += 1

    with open(filename, "w") as f:
        f.writelines(new_lines)

    print(f"Fixed {filename}")


if __name__ == "__main__":
    fix_repl_file("src/henchman/cli/repl.py")
