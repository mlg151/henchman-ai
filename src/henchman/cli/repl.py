### /home/matthew/mlg-cli/./src/henchman/cli/repl.py
### /home/matthew/mlg-cli/./src/henchman/cli/repl.py
3: 1: """REPL (Read-Eval-Print Loop) for interactive mode.
2: 
3: This module provides the main interactive loop for the CLI.
4: """
5: 
6: from __future__ import annotations
7: 
8: import asyncio
9: import sys
10: from collections.abc import AsyncIterator, Callable
11: from typing import Any
12: 
13: from rich.console import Console
14: from rich.live import Live
15: from rich.panel import Panel
16: from rich.status import Status
17: from rich.text import Text
18: 
19: # from henchman.cli.commands.base import CommandContext
# Temporary stub:
class CommandContext:
def __init__(self, console, args, agent, tool_registry, session):
self.console = console
self.args = args
self.agent = agent
self.tool_registry = tool_registry
self.session = session
20: # from henchman.cli.commands.registry import CommandRegistry
# Temporary stub:
class CommandRegistry:
    def __init__(self):
        self._commands = {}
    def get(self, name):
        return self._commands.get(name)
    def register(self, cmd):
        self._commands[cmd.name] = cmd
21: from henchman.cli.repl_toolbar import ReplToolbar
22: from henchman.cli.session import SessionManager
23: from henchman.core.agent import Agent
24: from henchman.core.events import AgentEvent, EventType
25: from henchman.providers.base import ModelProvider
26: from henchman.tools.registry import ToolRegistry
27: 
28: 
29: class ReplConfig:
30:     """Configuration for the REPL."""
31: 
32:     def __init__(
33:         self,
34:         system_prompt: str = "",
35:         show_thinking: bool = False,
36:         theme: str = "ansi",
37:     ) -> None:
38:         self.system_prompt = system_prompt
39:         self.show_thinking = show_thinking
40:         self.theme = theme
41: 
42: 
43: class Repl:
44:     """Interactive REPL for the CLI."""
45: 
46:     def __init__(
47:         self,
48:         provider: ModelProvider,
49:         config: ReplConfig | None = None,
50:         tool_registry: ToolRegistry | None = None,
51:         session_manager: SessionManager | None = None,
52:     ) -> None:
53:         self.provider = provider
54:         self.config = config or ReplConfig()
55:         self.tool_registry = tool_registry or ToolRegistry()
56:         self.session = session_manager
57:         
58:         self.console = Console()
59:         self.command_registry = CommandRegistry()
60:         self.toolbar = ReplToolbar()
61:         
62:         # Initialize agent with tool_registry
63:         self.agent = Agent(
64:             provider=provider,
65:             tool_registry=self.tool_registry,
66:             system_prompt=self.config.system_prompt,
67:         )
68:         
69:         self.agent_running = False
70:         self._agent_task: asyncio.Task[None] | None = None
71:         self._input_callback: Callable[[str], str] | None = None
72: 
73:     async def run(self) -> None:
74:         """Run the REPL main loop."""
75:         self.console.print(
76:             Panel(
77:                 Text("Henchman AI", style="bold green"),
78:                 title="Welcome",
79:                 border_style="green",
80:             )
81:         )
82:         
83:         while True:
84:             try:
85:                 # Get user input
86:                 user_input = await self._get_input()
87:                 if not user_input:
88:                     continue
89:                     
90:                 # Check if it's a command
91:                 if await self._try_command(user_input):
92:                     continue
93:                     
94:                 # Run agent
95:                 await self._run_agent(user_input)
96:                 
97:             except (KeyboardInterrupt, EOFError):
98:                 self.console.print("\nGoodbye!")
99:                 break
100:             except Exception as e:
101:                 self.console.print(f"[red]Error: {e}[/red]")
102: 
103:     async def _get_input(self) -> str:
104:         """Get input from user with toolbar."""
105:         # Simplified for now
106:         return input("> ")
107: 
108:     async def _try_command(self, user_input: str) -> bool:
109:         """Try to execute a command."""
110:         if user_input.startswith("/"):
111:             # Parse command
112:             parts = user_input[1:].strip().split(maxsplit=1)
113:             cmd_name = parts[0] if parts else ""
114:             args = parts[1] if len(parts) > 1 else ""
115:             
116:             cmd = self.command_registry.get(cmd_name)
117:             if cmd:
118:                 ctx = CommandContext(
119:                     console=self.console,
120:                     args=args,
121:                     agent=self.agent,
122:                     tool_registry=self.tool_registry,
123:                     session=self.session,
124:                 )
125:                 await cmd.execute(ctx)
126:                 return True
127:             else:
128:                 self.console.print(f"[yellow]Unknown command: /{cmd_name}[/yellow]")
129:                 return True
130:         return False
131: 
132:     async def _run_agent(self, user_input: str) -> None:
133:         """Run the agent with user input."""
134:         self.agent_running = True
135:         
136:         try:
137:             async for event in self.agent.run(user_input):
138:                 if event.type == EventType.CONTENT:
139:                     self.console.print(event.data, end="")
140:                 elif event.type == EventType.TOOL_CALL_REQUEST:
141:                     # Handle tool call
142:                     tool_call = event.data
143:                     self.console.print(f"[cyan]Tool call: {tool_call.name}[/cyan]")
144:                     
145:                     # Execute tool
146:                     if self.tool_registry:
147:                         result = await self.tool_registry.execute(
148:                             tool_call.name, tool_call.arguments
149:                         )
150:                         self.agent.submit_tool_result(tool_call.id, result)
151:         finally:
152:             self.agent_running = False
153:             self.console.print()  # New line after agent response
