import re

with open("src/henchman/cli/repl.py", "r") as f:
    content = f.read()

# Replace the entire _handle_tool_call method
old_method = """    async def _handle_tool_call(self, tool_call: ToolCall) -> None:
        \"\"\"Handle a tool call from the agent.

        Args:
            tool_call: The tool call to execute.
        \"\"\"
        if not isinstance(tool_call, ToolCall):
            return

        self.renderer.muted(f\"\\n[tool] {tool_call.name}({tool_call.arguments})\")

        # Execute the tool
        result = await self.tool_registry.execute(tool_call.name, tool_call.arguments)

        # Show result to user
        if result.display:
            self.renderer.info(result.display)
        elif result.success:
            self.renderer.success(f\"Tool {tool_call.name} executed successfully\")
        else:
            self.renderer.error(f\"Tool {tool_call.name} failed: {result.error}\")

        # Submit result to agent
        self.agent.submit_tool_result(tool_call.id, result.content)

        # Continue agent execution with tool result
        async for event in self.agent.continue_with_tool_results():
            await self._handle_agent_event(event)"""

new_method = """    async def _handle_tool_call(self, tool_call: ToolCall) -> None:
        \"\"\"Handle a tool call from the agent.

        Args:
            tool_call: The tool call to execute.
        \"\"\"
        if not isinstance(tool_call, ToolCall):
            return

        self.renderer.muted(f\"\\n[tool] {tool_call.name}({tool_call.arguments})\")

        # Execute the tool
        result = await self.tool_registry.execute(tool_call.name, tool_call.arguments)

        # Show result to user
        if result.display:
            self.renderer.info(result.display)
        elif result.success:
            self.renderer.success(f\"Tool {tool_call.name} executed successfully\")
        else:
            self.renderer.error(f\"Tool {tool_call.name} failed: {result.error}\")

        # Only submit result and continue execution if tool was successful
        if result.success:
            # Submit result to agent
            self.agent.submit_tool_result(tool_call.id, result.content)

            # Continue agent execution with tool results
            async for event in self.agent.continue_with_tool_results():
                await self._handle_agent_event(event)
        else:
            # Tool failed, don't submit result or continue execution
            # The agent will remain in its current state
            pass"""

# Use regex to replace
import re

pattern = r"""    async def _handle_tool_call(self, tool_call: ToolCall) -> None:.*?        async for event in self.agent.continue_with_tool_results():
            await self._handle_agent_event(event)"""
content = re.sub(pattern, new_method, content, flags=re.DOTALL)

with open("src/henchman/cli/repl.py", "w") as f:
    f.write(content)

print("Method replaced successfully")
