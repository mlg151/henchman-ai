### /home/matthew/mlg-cli/IMPLEMENTATION_PLAN.md
```markdown
### /home/matthew/mlg-cli/IMPLEMENTATION_PLAN.md
```markdown
1: # Henchman-AI Implementation Plan
2: 
3: > **A Model-Agnostic AI Agent CLI in Python**  
4: > Inspired by gemini-cli, built for extensibility  
5: > Primary Target: DeepSeek API (OpenAI-compatible)  
6: > **Created:** January 23, 2026
7: 
8: ---
9: 
10: ## Table of Contents
11: 
12: 1. [Executive Summary](#executive-summary)
13: 2. [Architecture Overview](#architecture-overview)
14: 3. [Phase 1: Project Foundation](#phase-1-project-foundation)
15: 4. [Phase 2: Provider System](#phase-2-provider-system)
16: 5. [Phase 3: Core Agent Loop](#phase-3-core-agent-loop)
17: 6. [Phase 4: Tool System](#phase-4-tool-system)
18: 7. [Phase 5: Built-in Tools](#phase-5-built-in-tools)
19: 8. [Phase 6: Configuration System](#phase-6-configuration-system)
20: 9. [Phase 7: Terminal UI](#phase-7-terminal-ui)
21: 10. [Phase 8: Session Management](#phase-8-session-management)
22: 11. [Phase 9: MCP Integration](#phase-9-mcp-integration)
23: 12. [Phase 10: Extensions & Plugins](#phase-10-extensions--plugins)
24: 11. [Phase 11: Advanced Features](#phase-11-advanced-features)
25: 12. [Phase 12: Polish & Release](#phase-12-polish--release)
26: 13. [Phase 13: Skills & Learning](#phase-13-skills--learning)
27: 14. [Phase 14: Enhanced Interaction & Context](#phase-14-enhanced-interaction--context)
28: 15. [Phase 15: Reinforced Memory System](#phase-15-reinforced-memory-system)
29: 16. [Technical Reference](#technical-reference)
30: 
31: ---
32: 
33: ## Executive Summary
34: 
35: ### Goal
36: 
37: Build a Python CLI agent that recreates gemini-cli functionality while being:
38: 
39: | Principle | Description |
40: |-----------|-------------|
41: | 🔄 **Model-Agnostic** | Support any LLM: DeepSeek, OpenAI, Anthropic, Ollama, etc. |
42: | 🐍 **Pythonic** | Leverage Python's async ecosystem and rich libraries |
43: | 🔌 **Extensible** | Plugin system for tools, providers, and commands |
44: | 🚀 **Production-Ready** | Proper error handling, testing, and packaging |
45: 
46: ### Key Insight: DeepSeek = OpenAI Compatible
47: 
48: ```python
49: from openai import OpenAI
50: 
51: client = OpenAI(
52:     api_key="your-key",
53:     base_url="https://api.deepseek.com"  # Just change this!
54: )
55: 
56: response = client.chat.completions.create(
57:     model="deepseek-chat",
58:     messages=[...],
59:     tools=[...],  # Function calling works!
60:     stream=True
61: )
62: ```
63: 
64: **One provider implementation handles**: DeepSeek, OpenAI, Together, Groq, Fireworks, and any OpenAI-compatible API.
65: 
66: ---
67: 
68: ## Architecture Overview
69: 
70: ```
71: ┌─────────────────────────────────────────────────────────────────────┐
72: │                           User Terminal                              │
73: └─────────────────────────────┬───────────────────────────────────────┘
74:                               │
75: ┌─────────────────────────────▼───────────────────────────────────────┐
76: │                      henchman/cli/ (UI Layer)                             │
77: │  • InputHandler (prompt_toolkit)    • OutputRenderer (rich)          │
78: │  • CommandParser (/commands)        • ThemeManager                   │
79: │  • ConfirmationDialogs              • StatusBar                      │
80: └─────────────────────────────┬───────────────────────────────────────┘
81:                               │
82: ┌─────────────────────────────▼───────────────────────────────────────┐
83: │                     henchman/core/ (Agent Layer)                          │
84: │  • AgentLoop (async generator)      • EventBus (typed events)        │
85: │  • ToolRegistry                     • PolicyEngine                   │
86: │  • SessionManager                   • ContextLoader (HENCHMAN.md)         │
87: └─────────────────────────────┬───────────────────────────────────────┘
88:                               │
89:          ┌────────────────────┼────────────────────┐
90:          │                    │                    │
91: ┌────────▼────────┐  ┌────────▼────────┐  ┌───────▼────────┐
92: │  henchman/providers/ │  │   henchman/tools/    │  │   henchman/mcp/     │
93: │  ┌───────────┐  │  │  ┌───────────┐  │  │ ┌───────────┐  │
94: │  │ OpenAI    │  │  │  │ ReadFile  │  │  │ │McpManager │  │
95: │  │ Compatible│──┼──│  │ WriteFile │  │  │ │McpClient  │  │
96: │  │ (DeepSeek)│  │  │  │ Shell     │  │  │ │McpTool    │  │
97: │  │ Anthropic │  │  │  │ WebFetch  │  │  │ └───────────┘  │
98: │  │ Ollama    │  │  │  │ Grep/Glob │  │  └────────────────┘
99: │  └───────────┘  │  │  └───────────┘  │
100: └─────────────────┘  └─────────────────┘
101: ```
102: 
103: ---
104: 
105: ## Phase 1: Project Foundation ✅
106: 
107: **Goal**: Set up project structure and dependencies
108: 
109: **Status**: COMPLETE (2026-01-23)
110: 
111: ### Tasks
112: 
113: - [x] **1.1** Create project directory structure
114: - [x] **1.2** Initialize `pyproject.toml` with dependencies
115: - [x] **1.3** Set up development tooling (ruff, mypy, pytest)
116: - [x] **1.4** Create basic `__main__.py` entry point
117: - [x] **1.5** Add README and LICENSE
118: 
119: ### Directory Structure
120: 
121: ```
122: henchman-ai/
123: ├── pyproject.toml
124: ├── README.md
125: ├── LICENSE
126: ├── src/
127: │   └── henchman/
128: │       ├── __init__.py
129: │       ├── __main__.py          # python -m henchman
130: │       ├── version.py
131: │       ├── cli/                 # UI Layer
132: │       ├── core/                # Agent Layer  
133: │       ├── providers/           # Model Providers
134: │       ├── tools/               # Built-in Tools
135: │       ├── mcp/                 # MCP Integration
136: │       ├── config/              # Configuration
137: │       └── utils/               # Utilities
138: ├── tests/
139: └── docs/
140: ```
141: 
142: ### Dependencies
143: 
144: ```toml
145: [project]
146: name = "henchman-ai"
147: version = "0.1.0"
148: requires-python = ">=3.11"
149: dependencies = [
150:     "httpx>=0.27",
151:     "openai>=1.40",
152:     "pydantic>=2.0",
153:     "rich>=13.0",
154:     "prompt-toolkit>=3.0",
155:     "anyio>=4.0",
156:     "click>=8.0",
157:     "pyyaml>=6.0",
158: ]
159: 
160: [project.scripts]
161: henchman = "henchman.cli.app:main"
162: ```
163: 
164: ### Acceptance Criteria
165: 
166: - `pip install -e .` works
167: - `henchman --version` prints version
168: - `henchman --help` shows help text
169: - All linting passes
170: 
171: ---
172: 
173: ## Phase 2: Provider System ✅
174: 
175: **Goal**: Abstract model providers with DeepSeek as primary target
176: 
177: **Status**: COMPLETE (2026-01-23)
178: 
179: ### Tasks
180: 
181: - [x] **2.1** Define `ModelProvider` protocol/ABC
182: - [x] **2.2** Define message and streaming types
183: - [x] **2.3** Implement `OpenAICompatibleProvider` base class
184: - [x] **2.4** Implement `DeepSeekProvider` (extends OpenAI-compatible)
185: - [x] **2.5** Create provider registry for discovery
186: - [x] **2.6** Add unit tests for providers (100% coverage)
187: 
188: ### Core Types
189: 
190: ```python
191: # henchman/providers/base.py
192: 
193: @dataclass
194: class Message:
195:     role: str  # "system" | "user" | "assistant" | "tool"
196:     content: str | None = None
197:     tool_calls: list[ToolCall] | None = None
198:     tool_call_id: str | None = None
199: 
200: @dataclass
201: class ToolCall:
202:     id: str
203:     name: str
204:     arguments: dict
205: 
206: @dataclass
207: class ToolDeclaration:
208:     name: str
209:     description: str
210:     parameters: dict  # JSON Schema
211: 
212: @dataclass
213: class StreamChunk:
214:     content: str | None = None
215:     tool_calls: list[ToolCall] | None = None
216:     finish_reason: FinishReason | None = None
217:     thinking: str | None = None  # For reasoning models
218: 
219: class ModelProvider(ABC):
220:     @property
221:     @abstractmethod
222:     def name(self) -> str: ...
223:     
224:     @abstractmethod
225:     async def chat_completion_stream(
226:         self,
227:         messages: list[Message],
228:         tools: list[ToolDeclaration] | None = None,
229:         **kwargs
230:     ) -> AsyncIterator[StreamChunk]: ...
231: ```
232: 
233: ### DeepSeek Implementation
234: 
235: ```python
236: # henchman/providers/deepseek.py
237: 
238: class DeepSeekProvider(OpenAICompatibleProvider):
239:     name = "deepseek"
240:     
241:     def __init__(self, api_key: str | None = None, model: str = "deepseek-chat"):
242:         super().__init__(
243:             api_key=api_key or os.environ.get("DEEPSEEK_API_KEY", ""),
244:             base_url="https://api.deepseek.com",
245:             default_model=model,
246:         )
247:     
248:     async def list_models(self) -> list[str]:
249:         return ["deepseek-chat", "deepseek-reasoner"]
250: ```
251: 
252: ### Acceptance Criteria
253: 
254: - Can instantiate DeepSeek provider
255: - Can stream a simple chat completion
256: - Tool declarations are properly formatted
257: - Provider works with/without API key env var
258: 
259: ---
260: 
261: ## Phase 3: Core Agent Loop ✅
262: 
263: **Goal**: Implement the main agent orchestration with event streaming
264: 
265: **Status**: COMPLETE (2026-01-23)
266: 
267: ### Tasks
268: 
269: - [x] **3.1** Define event types (`AgentEvent`, `EventType`)
270: - [x] **3.2** Implement basic `Agent` class
271: - [x] **3.3** Implement streaming with async generators
272: - [x] **3.4** Add conversation history management
273: - [x] **3.5** Implement tool call detection and routing
274: - [x] **3.6** Add unit tests for agent loop (100% coverage)
275: 
276: ### Event Types
277: 
278: ```python
279: # henchman/core/events.py
280: 
281: class EventType(Enum):
282:     CONTENT = auto()           # Text from model
283:     THOUGHT = auto()           # Reasoning content
284:     TOOL_CALL_REQUEST = auto() # Model wants a tool
285:     TOOL_CALL_RESULT = auto()  # Tool execution result
286:     TOOL_CONFIRMATION = auto() # Awaiting user approval
287:     ERROR = auto()
288:     FINISHED = auto()
289: 
290: @dataclass
291: class AgentEvent:
292:     type: EventType
293:     data: Any = None
294: ```
295: 
296: ### Agent Implementation
297: 
298: ```python
299: # henchman/core/agent.py
300: 
301: class Agent:
302:     def __init__(
303:         self,
304:         provider: ModelProvider,
305:         tool_registry: ToolRegistry,
306:         system_prompt: str = "",
307:     ):
308:         self.provider = provider
309:         self.tools = tool_registry
310:         self.history: list[Message] = []
311:     
312:     async def run(self, user_input: str) -> AsyncIterator[AgentEvent]:
313:         """Main agent loop - yields events as they occur"""
314:         self.history.append(Message(role="user", content=user_input))
315:         
316:         while True:
317:             # Stream from model
318:             async for chunk in self.provider.chat_completion_stream(
319:                 messages=self.history,
320:                 tools=self.tools.get_declarations(),
321:             ):
322:                 if chunk.content:
323:                     yield AgentEvent(EventType.CONTENT, chunk.content)
324:                 if chunk.tool_calls:
325:                     # Handle tool calls...
326:                     pass
327:             
328:             # If no tool calls, we're done
329:             if not pending_tool_calls:
330:                 yield AgentEvent(EventType.FINISHED)
331:                 break
332: ```
333: 
334: ### Acceptance Criteria
335: 
336: - Agent streams text responses
337: - Agent detects tool call requests
338: - History is maintained across turns
339: - Can handle multi-turn tool execution
340: 
341: ---
342: 
343: ## Phase 4: Tool System ✅
344: 
345: **Goal**: Implement extensible tool framework with confirmation policies
346: 
347: **Status**: COMPLETE (2026-01-23)
348: 
349: ### Tasks
350: 
351: - [x] **4.1** Define `Tool` base class
352: - [x] **4.2** Define `ToolResult` and `ConfirmationRequest` types
353: - [x] **4.3** Implement `ToolRegistry` for tool management
354: - [x] **4.4** Implement tool confirmation flow
355: - [x] **4.5** Implement `PolicyEngine` for auto-approval rules
356: - [x] **4.6** Add unit tests (100% coverage, 126 tests)
357: 
358: ### Tool Base Class
359: 
360: ```python
361: # henchman/tools/base.py
362: 
363: class ToolKind(Enum):
364:     READ = "read"       # Auto-approve (read_file, ls, glob)
365:     WRITE = "write"     # Requires confirmation (write_file, edit)
366:     EXECUTE = "execute" # Requires confirmation (shell)
367:     NETWORK = "network" # Requires confirmation (web_fetch)
368: 
369: @dataclass
370: class ToolResult:
371:     content: str           # Content for model
372:     success: bool = True
373:     display: str | None = None  # Different display for user
374:     error: str | None = None
375: 
376: class Tool(ABC):
377:     @property
378:     @abstractmethod
379:     def name(self) -> str: ...
380:     
381:     @property
382:     @abstractmethod
383:     def description(self) -> str: ...
384:     
385:     @property
386:     @abstractmethod
387:     def parameters(self) -> dict: ...  # JSON Schema
388:     
389:     @property
390:     def kind(self) -> ToolKind:
391:         return ToolKind.OTHER
392:     
393:     def needs_confirmation(self, params: dict) -> ConfirmationRequest | None:
394:         """Return confirmation request if needed"""
395:         if self.kind in (ToolKind.WRITE, ToolKind.EXECUTE):
396:             return ConfirmationRequest(...)
397:         return None
398:     
399:     @abstractmethod
400:     async def execute(self, **params) -> ToolResult: ...
401: ```
402: 
403: ### Tool Registry
404: 
405: ```python
406: # henchman/tools/registry.py
407: 
408: class ToolRegistry:
409:     def __init__(self):
410:         self._tools: dict[str, Tool] = {}
411:         self._confirmation_handler: Callable | None = None
412:     
413:     def register(self, tool: Tool) -> None: ...
414:     def get_declarations(self) -> list[ToolDeclaration]: ...
415:     async def execute(self, name: str, params: dict) -> ToolResult: ...
416: ```
417: 
418: ### Acceptance Criteria
419: 
420: - Can register and list tools
421: - Tool declarations generated correctly
422: - Confirmation flow works for write/execute tools
423: - Read tools auto-approved
424: 
425: ---
426: 
427: ## Phase 5: Built-in Tools ✅
428: 
429: **Goal**: Implement core tools matching gemini-cli functionality
430: 
431: **Status**: COMPLETE (2026-01-23) - ask_user deferred to UI phase
432: 
433: ### Tasks
434: 
435: - [x] **5.1** `read_file` - Read file contents with line ranges
436: - [x] **5.2** `write_file` - Create/overwrite files
437: - [x] **5.3** `edit_file` - Precise text replacements
438: - [x] **5.4** `ls` - List directory contents
439: - [x] **5.5** `glob` - Pattern-based file search
440: - [x] **5.6** `grep` - Text/regex search in files
441: - [x] **5.7** `shell` - Execute shell commands
442: - [x] **5.8** `web_fetch` - Fetch URL contents
443: - [x] **5.9** `ask_user` - Request user input (implemented with placeholder for REPL integration)
444: - [x] **5.10** Add tests for each tool (100% coverage, 214 tests)
445: 
446: ### Example: ReadFile Tool
447: 
448: ```python
449: # henchman/tools/file_read.py
450: 
451: class ReadFileTool(Tool):
452:     name = "read_file"
453:     description = "Read contents of a file"
454:     kind = ToolKind.READ
455:     
456:     parameters = {
457:         "type": "object",
458:         "properties": {
459:             "path": {"type": "string", "description": "File path"},
460:             "start_line": {"type": "integer", "default": 1},
461:             "end_line": {"type": "integer", "default": -1},
462:         },
463:         "required": ["path"]
464:     }
465:     
466:     async def execute(self, path: str, start_line: int = 1, end_line: int = -1) -> ToolResult:
467:         try:
468:             content = Path(path).read_text()
469:             lines = content.splitlines()[start_line-1:end_line if end_line > 0 else None]
470:             return ToolResult(content="\n".join(lines), success=True)
471:         except Exception as e:
472:             return ToolResult(content=f"Error: {e}", success=False, error=str(e))
473: ```
474: 
475: ### Example: Shell Tool
476: 
477: ```python
478: # henchman/tools/shell.py
479: 
480: class ShellTool(Tool):
481:     name = "run_shell_command"
482:     description = "Execute a shell command"
483:     kind = ToolKind.EXECUTE
484:     
485:     parameters = {
486:         "type": "object",
487:         "properties": {
488:             "command": {"type": "string"},
489:             "timeout": {"type": "integer", "default": 60},
490:         },
491:         "required": ["command"]
492:     }
493:     
494:     async def execute(self, command: str, timeout: int = 60) -> ToolResult:
495:         process = await asyncio.create_subprocess_shell(
496:             command,
497:             stdout=asyncio.subprocess.PIPE,
498:             stderr=asyncio.subprocess.PIPE,
499:             env={**os.environ, "HENCHMAN_CLI": "1"},
500:         )
501:         stdout, stderr = await asyncio.wait_for(process.communicate(), timeout)
502:         return ToolResult(
503:             content=f"Exit: {process.returncode}\n{stdout.decode()}{stderr.decode()}",
504:             success=process.returncode == 0,
505:         )
506: ```
507: 
508: ### Acceptance Criteria
509: 
510: - All tools execute correctly
511: - Error handling is robust
512: - Tools respect workspace boundaries
513: - Shell tool sets `HENCHMAN_CLI=1` env var
514: 
515: ---
516: 
517: ## Phase 6: Configuration System ✅
518: 
519: **Goal**: Hierarchical settings with YAML/JSON support
520: 
521: **Status**: COMPLETE (2026-01-23)
522: 
523: ### Tasks
524: 
525: - [x] **6.1** Define settings schema with Pydantic
526: - [x] **6.2** Implement settings file discovery
527: - [x] **6.3** Implement hierarchical merging
528: - [x] **6.4** Add environment variable overrides
529: - [x] **6.5** Implement context file (HENCHMAN.md) loading
530: - [x] **6.6** Add settings validation
531: - [x] **6.7** Add unit tests (100% coverage, 271 tests)
532: 
533: ### Settings Schema
534: 
535: ```python
536: # henchman/config/schema.py
537: 
538: class ProviderSettings(BaseModel):
539:     default: str = "deepseek"
540:     deepseek: dict = Field(default_factory=lambda: {"model": "deepseek-chat"})
541:     openai: dict = Field(default_factory=dict)
542:     anthropic: dict = Field(default_factory=dict)
543:     ollama: dict = Field(default_factory=lambda: {"base_url": "http://localhost:11434"})
544: 
545: class ToolSettings(BaseModel):
546:     auto_accept_read: bool = True
547:     shell_timeout: int = 60
548:     sandbox: Literal["none", "docker"] = "none"
549: 
550: class UISettings(BaseModel):
551:     theme: str = "dark"
552:     show_line_numbers: bool = True
553: 
554: class Settings(BaseModel):
555:     providers: ProviderSettings = Field(default_factory=ProviderSettings)
556:     tools: ToolSettings = Field(default_factory=ToolSettings)
557:     ui: UISettings = Field(default_factory=UISettings)
558:     mcp_servers: dict[str, McpServerConfig] = Field(default_factory=dict)
559: ```
560: 
561: ### Settings Loading
562: 
563: ```python
564: # henchman/config/settings.py
565: 
566: def load_settings() -> Settings:
567:     """Load settings with precedence: defaults < user < workspace < env"""
568:     settings = {}
569:     
570:     # User settings
571:     user_path = Path.home() / ".henchman" / "settings.yaml"
572:     if user_path.exists():
573:         settings = deep_merge(settings, yaml.safe_load(user_path.read_text()))
574:     
575:     # Workspace settings
576:     workspace_path = Path.cwd() / ".henchman" / "settings.yaml"
577:     if workspace_path.exists():
578:         settings = deep_merge(settings, yaml.safe_load(workspace_path.read_text()))
579:     
580:     # Environment overrides
581:     if provider := os.environ.get("HENCHMAN_PROVIDER"):
582:         settings.setdefault("providers", {})["default"] = provider
583:     
584:     return Settings(**settings)
585: ```
586: 
587: ### Context Loading (HENCHMAN.md + GitHub Copilot Instructions)
588: 
589: Context files provide project-specific instructions to the agent. Multiple formats are supported:
590: 
591: | File | Location | Purpose |
592: |------|----------|--------|
593: | `HENCHMAN.md` | `~/.henchman/`, ancestors, subdirs | MLG-native context |
594: | `.github/copilot-instructions.md` | Workspace root | GitHub Copilot compatibility |
595: 
596: ```python
597: # henchman/core/context.py
598: 
599: class ContextLoader:
600:     CONTEXT_FILES = [
601:         "HENCHMAN.md",
602:         ".github/copilot-instructions.md",
603:     ]
604:     
605:     def discover_files(self) -> list[Path]:
606:         """Find all context files in hierarchy"""
607:         files = []
608:         # Global: ~/.henchman/HENCHMAN.md
609:         # Workspace: .github/copilot-instructions.md
610:         # Ancestors: walk up to git root for HENCHMAN.md
611:         # Subdirectories: walk down respecting .gitignore
612:         return files
613:     
614:     def load(self) -> str:
615:         """Concatenate all context files"""
616:         return "\n\n---\n\n".join(
617:             f"# Context: {f}\n{f.read_text()}" 
618:             for f in self.discover_files()
619:         )
620: ```
621: 
622: ### Acceptance Criteria
623: 
624: - Settings load from correct locations
625: - Merge precedence works correctly
626: - Env vars override file settings
627: - HENCHMAN.md files discovered and concatenated
628: - `.github/copilot-instructions.md` loaded when present
629: 
630: ---
631: 
632: ## Phase 7: Terminal UI ✅
633: 
634: **Goal**: Rich terminal interface with streaming output
635: 
636: **Status**: COMPLETE (2026-01-23)
637: 
638: ### Tasks
639: 
640: - [x] **7.1** Set up Rich console and themes (Theme, ThemeManager, OutputRenderer)
641: - [x] **7.2** Implement input handling with prompt_toolkit (InputHandler)
642: - [x] **7.3** Implement streaming markdown output
643: - [x] **7.4** Implement tool confirmation dialogs (framework ready)
644: - [x] **7.5** Add status bar with context info
645: - [x] **7.6** Implement slash command parsing (Command, CommandRegistry, builtins)
646: - [x] **7.7** Implement at-command (@file) parsing
647: - [x] **7.8** Implement shell mode (!)
648: - [x] **7.9** Add unit tests (100% coverage, 363 tests)
649: 
650: ### Main CLI Loop
651: 
652: ```python
653: # henchman/cli/app.py
654: 
655: async def run_cli():
656:     console = Console()
657:     settings = load_settings()
658:     provider = create_provider(settings)
659:     tools = create_tool_registry(settings)
660:     agent = Agent(provider, tools, system_prompt=load_context())
661:     
662:     session = PromptSession(history=FileHistory(".henchman_history"))
663:     
664:     console.print("[bold blue]MLG CLI[/] - /help for commands, /quit to exit\n")
665:     
666:     while True:
667:         try:
668:             user_input = await asyncio.to_thread(session.prompt, "❯ ")
669:             
670:             # Handle commands
671:             if user_input.startswith("/"):
672:                 await handle_slash_command(user_input, console)
673:                 continue
674:             if user_input.startswith("!"):
675:                 await handle_shell_command(user_input, console)
676:                 continue
677:             
678:             # Expand @file references
679:             user_input = await expand_at_references(user_input)
680:             
681:             # Run agent
682:             async for event in agent.run(user_input):
683:                 await render_event(event, console)
684:                 
685:         except KeyboardInterrupt:
686:             console.print("\n[dim]Interrupted[/]")
687:         except EOFError:
688:             break
689: ```
690: 
691: ### Slash Commands
692: 
693: ```python
694: # henchman/cli/commands/
695: 
696: /help      - Show help
697: /quit      - Exit CLI
698: /model     - Select model
699: /provider  - Select provider
700: /settings  - Open settings
701: /chat save/resume/list - Session management
702: /memory show/refresh   - Context management
703: /tools     - List available tools
704: /clear     - Clear screen
705: ```
706: 
707: ### Acceptance Criteria
708: 
709: - Streaming output renders smoothly
710: - Markdown syntax highlighting works
711: - Tool confirmations show clearly
712: - Commands parse correctly
713: - @file references expand inline
714: 
715: ---
716: 
717: 
## UI Integration Testing Strategy
### Problem Statement
After fixing the major bug where Henchman-AI was operating as a chatbot without tool access, we need to ensure ALL functionality is properly attached to the UI, including all slash commands. The current test coverage shows significant gaps in UI-component integration.
### Testing Philosophy
1. **Comprehensive Coverage**: Every UI feature must have corresponding integration tests
2. **End-to-End Validation**: Tests should verify the complete flow from user input to system response
3. **Regression Prevention**: Tests should catch disconnections between UI and underlying components
4. **Granular Verification**: Each slash command, tool, and feature must be individually tested
### Testing Pyramid for Henchman-AI
```
UI Integration Tests
• Complete REPL flow with all slash commands
• Tool execution through UI
• Command parsing and execution
• Session management through UI
│
Component Integration Tests
• REPL ↔ Agent connection
• REPL ↔ ToolRegistry connection
• CommandRegistry ↔ Command execution
• Agent ↔ Provider communication
│
Unit Tests
• Individual tool implementations
• Command parsing logic
• Agent event handling
• Provider implementations
```
### Test Categories to Implement
#### 1. Slash Command Integration Tests
**Objective**: Verify all slash commands are properly connected to their implementations
| Command | Test Focus | Expected Behavior |
|---------|------------|-------------------|
| /help | Command discovery and display | Shows available commands with descriptions |
| /quit | REPL lifecycle | Cleanly exits the REPL loop |
| /clear | UI state management | Clears agent history and console |
| /tools | Tool registry integration | Lists all available tools with descriptions |
| /chat | Session management | Starts new chat session with proper context |
| /extensions | Extension system | Lists loaded extensions and their tools |
| /mcp | MCP integration | Shows MCP server status and available tools |
| /plan | Planning mode | Toggles/enables planning mode |
| /skill | Skill system | Lists available skills and their usage |
#### 2. Tool Execution Integration Tests
**Objective**: Verify tools can be executed through the UI
| Tool | Test Scenario | Verification Points |
|------|---------------|---------------------|
| read_file | Agent requests file reading | File content returned to UI |
| write_file | Agent creates/modifies files | File system changes confirmed |
| shell | Agent executes commands | Command output displayed |
| grep | Agent searches files | Search results returned |
| ls | Agent lists directory | Directory contents displayed |
| glob | Agent uses patterns | Pattern matching results shown |
| web_fetch | Agent fetches URLs | Web content retrieved |
| ask_user | Agent requests input | User prompt displayed and response captured |
#### 3. REPL-Component Integration Tests
**Objective**: Verify REPL properly connects all components
| Component Connection | Test Method | Success Criteria |
|----------------------|-------------|------------------|
| REPL ↔ Agent | Mock agent events | Events properly routed to UI |
| REPL ↔ ToolRegistry | Tool listing/execution | Tools available and executable |
| REPL ↔ CommandRegistry | Command execution | Commands properly dispatched |
| REPL ↔ SessionManager | Session persistence | Sessions saved/loaded correctly |
| REPL ↔ OutputRenderer | Display formatting | Output properly formatted |
#### 4. End-to-End User Flow Tests
**Objective**: Verify complete user interactions work
| User Flow | Test Steps | Expected Outcome |
|-----------|------------|------------------|
| Tool execution flow | User input → Agent → Tool call → Result display | Complete tool execution with UI feedback |
| Command execution flow | Slash command → Command parsing → Execution → Response | Command executed with proper output |
| Session persistence flow | Start session → Add messages → Save → Load → Continue | Session state preserved |
| Multi-turn conversation | Multiple user inputs with tool calls | Context maintained across turns |
### Implementation Plan for UI Integration Tests
#### Phase 1: Foundation (Current Sprint)
1. **Create test infrastructure**
- tests/ui_integration/ directory structure
- Base test classes for UI integration
- Mock providers for deterministic testing
- Test fixtures for REPL components
2. **Implement slash command tests**
- Test each built-in command individually
- Verify command parsing and routing
- Test error handling for invalid commands
#### Phase 2: Tool Integration (Next Sprint)
1. **Tool execution through UI tests**
- Test each built-in tool via agent interaction
- Verify tool results are displayed in UI
- Test tool error handling and display
2. **REPL component connection tests**
- Verify REPL initializes all components correctly
- Test component communication pathways
- Validate event flow through the system
#### Phase 3: End-to-End Flows (Following Sprint)
1. **Complete user flow tests**
- Test realistic user scenarios
- Verify multi-step interactions work
- Test session persistence flows
2. **Edge case and error handling**
- Test error conditions and recovery
- Verify graceful degradation
- Test resource cleanup
### Test Implementation Details
#### Directory Structure
```
tests/ui_integration/
├── __init__.py
├── conftest.py              # Test fixtures
├── test_slash_commands.py   # Slash command tests
├── test_tool_integration.py # Tool execution tests  
├── test_repl_integration.py # REPL component tests
├── test_e2e_flows.py       # End-to-end user flows
└── test_error_handling.py  # Error condition tests
```
#### Key Test Fixtures
```python
@pytest.fixture
def mock_provider():
"""Mock provider that returns deterministic responses."""
provider = Mock(spec=ModelProvider)
# Configure mock responses
return provider
@pytest.fixture 
def repl_with_tools(mock_provider):
"""REPL instance with all tools registered."""
console = Console(record=True)
repl = Repl(provider=mock_provider, console=console)
return repl
@pytest.fixture
async def running_repl(repl_with_tools):
"""REPL instance in running state."""
# Start REPL in background
task = asyncio.create_task(repl_with_tools.run())
yield repl_with_tools
# Cleanup
task.cancel()
```
#### Example Test: Slash Command Integration
```python
async def test_slash_help_command(running_repl):
"""Test /help command shows available commands."""
# Simulate user typing /help
result = await running_repl._handle_command("/help")
# Verify command was handled
assert result is True
# Check console output contains command list
output = running_repl.console.export_text()
assert "/help" in output
assert "/quit" in output
assert "Available commands" in output
```
#### Example Test: Tool Execution Through UI
```python
async def test_tool_execution_flow(running_repl, tmp_path):
"""Test complete tool execution flow through UI."""
# Create test file
test_file = tmp_path / "test.txt"
test_file.write_text("Hello World")
# Configure mock agent to request file read
def mock_agent_response():
return ToolCall(
tool_name="read_file",
arguments={"path": str(test_file)}
)
running_repl.agent.get_next_tool_call = mock_agent_response
# Simulate user asking to read file
await running_repl._run_agent("Read the test file")
# Verify file content was read and displayed
output = running_repl.console.export_text()
assert "Hello World" in output
assert "test.txt" in output
```
### Success Metrics
1. **Test Coverage Goals**
- 100% of slash commands have integration tests
- 100% of built-in tools have UI integration tests  
- 90%+ line coverage for UI layer (cli/ directory)
- All component connections verified
2. **Quality Gates**
- No UI feature without corresponding integration test
- All tests pass before merging to main
- Tests run in CI pipeline with each commit
- Code coverage reports generated automatically
3. **Regression Prevention**
- Tests detect component disconnections
- UI changes require corresponding test updates
- Breaking changes caught before deployment
### Integration with Existing Test Suite
The UI integration tests will complement the existing test structure:
```
tests/
├── cli/                    # Existing CLI unit tests
├── core/                   # Core component tests  
├── tools/                  # Tool unit tests
├── providers/              # Provider tests
├── integration/            # Component integration tests
└── ui_integration/         # NEW: UI integration tests
├── test_slash_commands.py
├── test_tool_integration.py
└── test_e2e_flows.py
```
### Implementation Timeline
**Week 1**: Foundation and slash command tests
- Create test infrastructure
- Implement all slash command integration tests
- Add to CI pipeline
**Week 2**: Tool integration tests  
- Implement tool execution through UI tests
- Test REPL component connections
- Expand test coverage
**Week 3**: End-to-end flows and polish
- Implement complete user flow tests
- Add error handling tests
- Finalize test documentation
- Achieve coverage targets
### Maintenance and Evolution
1. **Test Maintenance**
- Tests updated with new features
- Regular test reviews and refactoring
- Performance optimization for test suite
2. **Test-Driven Development**
- New features require integration tests
- Tests written before implementation
- Tests serve as documentation
3. **Continuous Improvement**
- Regular test suite performance reviews
- Test coverage monitoring
- Feedback loop from test failures
This comprehensive UI integration testing strategy ensures that Henchman-AI remains robust, maintainable, and provides a seamless user experience with all functionality properly connected to the UI interface.
## Phase 8: Session Management ✅
718: 
719: **Goal**: Save and restore conversation sessions
720: 
721: **Status**: Completed January 2026
722: 
723: ### Tasks
724: 
725: - [x] **8.1** Define session data model
726: - [x] **8.2** Implement session persistence (JSON)
727: - [x] **8.3** Implement `/chat save <tag>`
728: - [x] **8.4** Implement `/chat resume <tag>`
729: - [x] **8.5** Implement `/chat list`
730: - [x] **8.6** Add auto-save on exit (deferred to main loop integration)
731: 
732: ### Session Model
733: 
734: ```python
735: # henchman/core/session.py
736: 
737: @dataclass
738: class SessionMessage:
739:     role: str
740:     content: str | None = None
741:     tool_calls: list[dict[str, Any]] | None = None
742:     tool_call_id: str | None = None
743: 
744: @dataclass
745: class SessionMetadata:
746:     id: str
747:     tag: str | None
748:     project_hash: str
749:     started: str
750:     last_updated: str
751:     message_count: int
752: 
753: @dataclass
754: class Session:
755:     id: str
756:     project_hash: str
757:     started: str
758:     last_updated: str
759:     messages: list[SessionMessage]
760:     tag: str | None = None
761:     
762: class SessionManager:
763:     def __init__(self, data_dir: Path = None):
764:         self.data_dir = data_dir or (Path.home() / ".henchman" / "sessions")
765:     
766:     def create_session(self, project_hash: str, tag: str | None = None) -> Session: ...
767:     def save(self, session: Session) -> Path: ...
768:     def load(self, session_id: str) -> Session: ...
769:     def load_by_tag(self, tag: str, project_hash: str | None = None) -> Session | None: ...
770:     def list_sessions(self, project_hash: str | None = None) -> list[SessionMetadata]: ...
771:     def delete(self, session_id: str) -> None: ...
772:     def compute_project_hash(self, directory: Path) -> str: ...
773: ```
774: 
775: ### Acceptance Criteria
776: 
777: - ✅ Sessions save with all messages
778: - ✅ Sessions restore history correctly
779: - ✅ Project-scoped session listing
780: - ⏳ Auto-save on graceful exit (requires Phase 12 main loop)
781: 
782: ---
783: 
784: ## Phase 9: MCP Integration ✅
785: 
786: **Goal**: Support Model Context Protocol servers
787: 
788: **Status**: Completed January 2026
789: 
790: ### Tasks
791: 
792: - [x] **9.1** Add `mcp` package dependency
793: - [x] **9.2** Implement `McpClient` for single server
794: - [x] **9.3** Implement `McpManager` for multiple servers
795: - [x] **9.4** Implement `McpTool` wrapper as internal Tool
796: - [x] **9.5** Add MCP server configuration (McpServerConfig)
797: - [x] **9.6** Implement `/mcp list` and `/mcp status` commands
798: 
799: ### MCP Configuration
800: 
801: ```yaml
802: # ~/.henchman/settings.yaml
803: mcp_servers:
804:   filesystem:
805:     command: npx
806:     args: ["@anthropic-ai/mcp-filesystem-server", "/home/user"]
807:     trusted: false
808:   
809:   github:
810:     command: uvx
811:     args: ["mcp-github"]
812:     env:
813:       GITHUB_TOKEN: "${GITHUB_TOKEN}"
814:     trusted: true
815: ```
816: 
817: ### MCP Client
818: 
819: ```python
820: # henchman/mcp/client.py
821: 
822: class McpClient:
823:     def __init__(self, name: str, config: McpServerConfig):
824:         self.name = name
825:         self.config = config
826:     
827:     async def connect(self) -> None:
828:         """Connect via stdio transport"""
829:         ...
830:     
831:     async def discover_tools(self) -> list[McpTool]:
832:         """Get tools from server"""
833:         ...
834:     
835:     async def call_tool(self, name: str, args: dict) -> Any:
836:         """Execute tool on server"""
837:         ...
838: ```
839: 
840: ### Acceptance Criteria
841: 
842: - ✅ Can connect to MCP servers
843: - ✅ Tools discovered and registered
844: - ✅ Tool execution works through MCP
845: - ✅ Trusted servers skip confirmation (use ToolKind.READ)
846: 
847: ---
848: 
849: ## Phase 10: Extensions & Plugins ✅
850: 
851: **Goal**: Allow third-party extensions
852: 
853: ### Tasks
854: 
855: - [x] **10.1** Define `Extension` base class
856: - [x] **10.2** Implement entry point discovery
857: - [x] **10.3** Implement directory-based extensions
858: - [x] **10.4** Create extension loading system
859: - [x] **10.5** Implement `/extensions` command
860: 
861: ### Extension Interface
862: 
863: ```python
864: # henchman/extensions/base.py
865: 
866: class Extension(ABC):
867:     @property
868:     def name(self) -> str: ...
869:     @property
870:     def version(self) -> str: ...
871:     @property
872:     def description(self) -> str: ...
873:     
874:     def get_tools(self) -> list[Tool]:
875:         """Return tools provided by this extension"""
876:         return []
877:     
878:     def get_commands(self) -> list[Command]:
879:         """Return slash commands"""
880:         return []
881:     
882:     def get_context(self) -> str:
883:         """Additional system prompt context"""
884:         return ""
885: ```
886: 
887: ### Extension Discovery
888: 
889: ```python
890: # Entry points in pyproject.toml
891: [project.entry-points."henchman.extensions"]
892: my_extension = "my_package:MyExtension"
893: 
894: # Directory-based
895: ~/.henchman/extensions/my-ext/extension.py
896: ```
897: 
898: ### ExtensionManager Usage
899: 
900: ```python
901: from henchman.extensions import Extension, ExtensionManager
902: from pathlib import Path
903: 
904: # Create manager and discover extensions
905: manager = ExtensionManager()
906: manager.discover_entry_points()  # From installed packages
907: manager.discover_directory(Path.home() / ".henchman" / "extensions")
908: 
909: # Use discovered extensions
910: tools = manager.get_all_tools()
911: commands = manager.get_all_commands()
912: context = manager.get_combined_context()
913: ```
914: 
915: ### Acceptance Criteria
916: 
917: - ✅ Entry point extensions load
918: - ✅ Directory extensions load
919: - ✅ Extension tools register correctly
920: - ✅ Extension commands work
921: 
922: ---
923: 
924: ## Phase 11: Advanced Features (Partial)
925: 
926: **Goal**: Implement remaining gemini-cli features
927: 
928: ### Tasks
929: 
930: - [ ] **11.1** Checkpointing (file state snapshots before edits) - DEFERRED
931: - [ ] **11.2** Sandboxing (Docker container execution) - DEFERRED
932: - [ ] **11.3** Hooks system (before/after events) - DEFERRED
933: - [x] **11.4** Headless mode (`--prompt` flag) - ✅ Implemented in Phase 12
934: - [x] **11.5** JSON output mode (`--output-format json`) - ✅ Implemented in Phase 12
935: - [x] **11.6** Multiple providers (Anthropic, Ollama) ✅
936: 
937: ### Implemented: Multiple Providers
938: 
939: #### AnthropicProvider
940: 
941: Native Claude SDK integration with streaming support:
942: 
943: ```python
944: from henchman.providers import AnthropicProvider
945: 
946: provider = AnthropicProvider(api_key="sk-ant-...", model="claude-sonnet-4-20250514")
947: async for chunk in provider.chat_completion_stream(messages):
948:     print(chunk.content, end="")
949: ```
950: 
951: Supported models:
952: - claude-sonnet-4-20250514 (default)
953: - claude-3-7-sonnet-20250219
954: - claude-3-5-sonnet-20241022
955: - claude-3-5-haiku-20241022
956: - claude-3-opus-20240229
957: 
958: #### OllamaProvider
959: 
960: Local model support via Ollama's OpenAI-compatible API:
961: 
962: ```python
963: from henchman.providers import OllamaProvider
964: 
965: provider = OllamaProvider(model="llama3.2")  # No API key needed
966: async for chunk in provider.chat_completion_stream(messages):
967:     print(chunk.content, end="")
968: ```
969: 
970: ### Headless Mode
971: 
972: ```bash
973: # Simple prompt
974: henchman --prompt "Explain this code" < file.py
975: 
976: # JSON output for scripting
977: henchman -p "Summarize README.md" --output-format json
978: 
979: # Streaming JSON for real-time
980: henchman -p "Run tests" --output-format stream-json
981: ```
982: 
983: ### Hooks System
984: 
985: ```python
986: # ~/.henchman/hooks/before_tool/validate.py
987: # Receives JSON on stdin, outputs JSON on stdout
988: # Exit 0 = allow, Exit 2 = block
989: 
990: class HookRunner:
991:     async def run(self, event: HookEvent, data: dict) -> HookResult:
992:         """Run all hooks for event"""
993:         ...
994: ```
995: 
996: ### Acceptance Criteria
997: 
998: - Checkpoints save/restore file state
999: - Sandbox executes commands in Docker
1000: - Hooks intercept and can block actions
1001: - Headless mode works for scripting
1002: 
1003: ---
1004: 
1005: ## Phase 13: Skills & Learning (Partial) ✅
1006: 
1007: **Goal**: Enable agent to learn and reuse successful task patterns
1008: 
1009: ### Tasks
1010: 
1011: - [x] **13.1** Define `Skill` model and `SkillStep` types
1012: - [x] **13.2** Implement `SkillStore` with git-backed storage
1013: - [ ] **13.3** Implement `SkillLearner` for extracting skills from sessions
1014: - [ ] **13.4** Implement `SkillExecutor` for replaying skills
1015: - [ ] **13.5** Add skill detection heuristics to agent
1016: - [ ] **13.6** Implement `/skill` commands (list, show, run, delete, etc.)
1017: - [ ] **13.7** Support `.github/skills/` directory format
1018: - [ ] **13.8** Add skill import/export and remote sync
1019: - [x] Verification: Skills engine handles errors and replaying correctly (Models and Store verified)
1020: 
1021: ### Skill Storage Formats
1022: 
1023: Skills can be stored in two formats:
1024: 
1025: | Format | Location | Use Case |
1026: |--------|----------|----------|
1027: | YAML | `~/.henchman/skills/*.skill.yaml` | User-learned skills |
1028: | Markdown | `.github/skills/<name>/SKILL.md` | Shareable, repo-committed skills |
1029: 
1030: ### YAML Format (User Skills)
1031: 
1032: ```yaml
1033: # ~/.henchman/skills/add-api-endpoint.skill.yaml
1034: name: add-api-endpoint
1035: description: Create a new REST API endpoint with router, handler, and tests
1036: version: 1
1037: created: 2026-01-23T10:30:00Z
1038: author: matthew
1039: tags: [api, fastapi, backend]
1040: 
1041: triggers:
1042:   - "add a new endpoint"
1043:   - "create an API route"
1044: 
1045: parameters:
1046:   resource:
1047:     description: "Name of the resource (e.g., users, products)"
1048:     required: true
1049: 
1050: steps:
1051:   - description: "Create router file"
1052:     tool: write_file
1053:     arguments:
1054:       path: "src/api/routers/{{resource}}.py"
1055:       content: |
1056:         from fastapi import APIRouter
1057:         router = APIRouter(prefix="/{{resource}}")
1058: ```
1059: 
1060: ### Markdown Format (GitHub Skills)
1061: 
1062: ```markdown
1063: <!-- .github/skills/add-endpoint/SKILL.md -->
1064: # add-endpoint
1065: 
1066: Create a new REST API endpoint with router and tests.
1067: 
1068: ## Triggers
1069: 
1070: - "add a new endpoint"
1071: - "create an API route for {resource}"
1072: 
1073: ## Parameters
1074: 
1075: | Name | Required | Description |
1076: |------|----------|-------------|
1077: | resource | yes | Name of the resource |
1078: | methods | no | HTTP methods (default: GET, POST) |
1079: 
1080: ## Steps
1081: 
1082: ### 1. Create router file
1083: 
1084: **Tool:** `write_file`
1085: 
1086: ```python
1087: # Path: src/api/routers/{{resource}}.py
1088: from fastapi import APIRouter
1089: 
1090: router = APIRouter(prefix="/{{resource}}", tags=["{{resource}}"])
1091: 
1092: @router.get("/")
1093: async def list_{{resource}}():
1094:     return []
1095: ```
1096: 
1097: ### 2. Register router
1098: 
1099: **Tool:** `edit_file`
1100: 
1101: Add import and include router in `src/api/main.py`.
1102: ```
1103: 
1104: ### Git-Backed Storage
1105: 
1106: ```python
1107: # henchman/skills/storage.py
1108: 
1109: class SkillStore:
1110:     def __init__(self, path: Path = None):
1111:         self.path = path or Path.home() / ".henchman" / "skills"
1112:         self._ensure_git_repo()
1113:     
1114:     def _ensure_git_repo(self) -> None:
1115:         """Initialize git repo for version history"""
1116:         if not (self.path / ".git").exists():
1117:             subprocess.run(["git", "init"], cwd=self.path)
1118:     
1119:     def save(self, skill: Skill, message: str = None) -> None:
1120:         """Save skill and commit to git"""
1121:         ...
1122:     
1123:     def history(self, skill_name: str) -> list[SkillVersion]:
1124:         """Get version history from git log"""
1125:         ...
1126:     
1127:     def rollback(self, skill_name: str, commit: str) -> None:
1128:         """Restore skill to previous version"""
1129:         ...
1130: ```
1131: 
1132: ### Agent Behavior
1133: 
1134: **Learning** (agent-initiated):
1135: ```
1136: ✅ Done! I created the products endpoint.
1137: 
1138: 💡 This looks like a reusable pattern. Should I remember this as a skill?
1139:    [Yes, save skill] [No thanks]
1140: ```
1141: 
1142: **Usage** (agent-driven with announcement):
1143: ```
1144: ❯ I need an orders endpoint
1145: 
1146: 🎯 Using learned skill: add-api-endpoint
1147:    Parameters: resource=orders
1148: ```
1149: 
1150: ### Slash Commands
1151: 
1152: ```
1153: /skill list                    # List all skills
1154: /skill show <name>             # Show skill steps
1155: /skill run <name> [--param=val]  # Execute skill
1156: /skill history <name>          # Version history (git log)
1157: /skill rollback <name> <hash>  # Restore version
1158: /skill edit <name>             # Open in $EDITOR
1159: /skill delete <name>           # Remove skill
1160: /skill export <name>           # Print to stdout
1161: /skill import <path|url>       # Import from file/URL
1162: /skill remote [add|push|pull]  # Git remote sync
1163: ```
1164: 
1165: ### Acceptance Criteria
1166: 
1167: - Skills save in YAML format with git commits
1168: - `.github/skills/*/SKILL.md` files discovered and loaded
1169: - Agent offers to save skill-worthy completions
1170: - Agent announces when using learned skills
1171: - Skills shareable via export/import or git remotes
1172: - Verification: Skills engine handles errors and replaying correctly
1173: 
1174: ---
1175: 
1176: ## Phase 14: Enhanced Interaction & Context ✅
1177: 
1178: **Goal**: Improve user control, safety, and context awareness
1179: 
1180: **Status**: COMPLETE (2026-01-23)
1181: 
1182: ### Tasks
1183: 
1184: - [x] **14.1** **Escape Key Support**
1185:     - [x] 14.1.1 Bind `Keys.Escape` in `InputHandler` (prompt_toolkit) to cancel signal
1186:     - [x] 14.1.2 Implement async cancellation in `Agent.run` loop
1187:     - [x] 14.1.3 Ensure `Tool.execute` respects cancellation (timeouts/interrupts)
1188:     - [x] 14.1.4 UX: Visual feedback for cancelled operations
1189: 
1190: - [x] **14.2** **Plan Mode** (`/plan`)
1191:     - [x] 14.2.1 Implement `/plan` toggle command
1192:     - [x] 14.2.2 Create `PlanMode` state in Session
1193:     - [x] 14.2.3 Enforce "Read-Only" policy in `PolicyEngine` when in Plan Mode
1194:     - [x] 14.2.4 Allow writing to temporary/scratchpad areas only
1195:     - [x] 14.2.5 System Prompt injection: "You are in PLAN MODE..."
1196:     - [x] 14.2.6 UX: Yellow/Distinct theme or status indicator for Plan Mode
1197: 
1198: - [x] **14.3** **Context Intelligence**
1199:     - [x] 14.3.1 Implement `TokenCounter` utility
1200:     - [x] 14.3.2 Display "Tokens: Used/Max" in Status Bar
1201:     - [x] 14.3.3 Implement `ContextCompactor` (Summary/Pruning strategies)
1202:     - [x] 14.3.4 Add configuration for auto-compaction thresholds
1203: 
1204: ---
1205: 
1206: ## Phase 15: Reinforced Memory System
1207: 
1208: **Goal**: Enable agent to build persistent, weighted memory that strengthens through use
1209: 
1210: ### Overview
1211: 
1212: Memory uses a reinforcement model where facts gain strength when used successfully and decay when unused, mimicking human memory patterns.
1213: 
1214: ### Tasks
1215: 
1216: - [ ] **15.1** Define `Fact` model with weight, uses, decay_rate
1217: - [ ] **15.2** Implement `ReinforcedMemory` store with YAML persistence
1218: - [ ] **15.3** Implement reinforcement logic (strengthen on success, weaken on failure)
1219: - [ ] **15.4** Implement Ebbinghaus decay curve for unused memories
1220: - [ ] **15.5** Add `remember` tool for agent to store facts
1221: - [ ] **15.6** Add `memory_feedback` tool for explicit reinforcement
1222: - [ ] **15.7** Integrate memory into system prompt via `ContextLoader`
1223: - [ ] **15.8** Implement `/memory` commands (show, add, forget, prune)
1224: - [ ] **15.9** Add memory visualization in REPL status
1225: 
1226: ### Memory Model
1227: 
1228: ```python
1229: # henchman/core/memory.py
1230: 
1231: @dataclass
1232: class Fact:
1233:     id: str
1234:     content: str
1235:     weight: float = 1.0          # Strength (0-10)
1236:     uses: int = 0                # Times recalled
1237:     created: datetime
1238:     last_used: datetime
1239:     decay_rate: float = 0.1      # Daily decay when unused
1240:     scope: Literal["project", "user"] = "project"
1241:     
1242:     def reinforce(self, success: bool = True) -> None:
1243:         """Strengthen or weaken based on outcome"""
1244:         self.uses += 1
1245:         self.last_used = datetime.now()
1246:         
1247:         if success:
1248:             # Diminishing returns: harder to strengthen strong memories
1249:             boost = 1.0 / (1 + self.weight * 0.1)
1250:             self.weight = min(10.0, self.weight + boost)
1251:         else:
1252:             self.weight = max(0.0, self.weight - 0.5)
1253:     
1254:     def apply_decay(self) -> None:
1255:         """Ebbinghaus forgetting curve - strong memories decay slower"""
1256:         days_unused = (datetime.now() - self.last_used).days
1257:         if days_unused > 0:
1258:             decay = self.decay_rate * (1 / (1 + self.weight * 0.1))
1259:             self.weight = max(0.0, self.weight - (decay * days_unused))
1260: ```
1261: 
1262: ### Memory Storage
1263: 
1264: ```yaml
1265: # .henchman/memory.yaml (project) or ~/.henchman/memory.yaml (user)
1266: facts:
1267:   - id: f_001
1268:     content: "API routes go in src/api/routers/"
1269:     weight: 8.5
1270:     uses: 12
1271:     created: 2026-01-15T10:30:00Z
1272:     last_used: 2026-01-23T14:22:00Z
1273:     decay_rate: 0.1
1274:     
1275:   - id: f_002
1276:     content: "User prefers pytest over unittest"
1277:     weight: 2.3
1278:     uses: 2
1279:     created: 2026-01-20T09:00:00Z
1280:     last_used: 2026-01-21T11:00:00Z
1281:     decay_rate: 0.1
1282: ```
1283: 
1284: ### ReinforcedMemory Manager
1285: 
1286: ```python
1287: class ReinforcedMemory:
1288:     def __init__(self, project_path: Path, user_path: Path):
1289:         self.project_path = project_path / ".henchman" / "memory.yaml"
1290:         self.user_path = user_path / ".henchman" / "memory.yaml"
1291:         self.recall_threshold = 1.0  # Minimum weight to include
1292:     
1293:     def recall(self, limit: int = 20) -> list[Fact]:
1294:         """Get facts above threshold, sorted by weight"""
1295:         self.apply_all_decay()
1296:         active = [f for f in self.facts if f.weight >= self.recall_threshold]
1297:         active.sort(key=lambda f: f.weight, reverse=True)
1298:         return active[:limit]
1299:     
1300:     def remember(self, content: str, scope: str = "project") -> Fact:
1301:         """Add new fact or reinforce existing similar fact"""
1302:         existing = self._find_similar(content)
1303:         if existing:
1304:             existing.reinforce(success=True)
1305:             return existing
1306:         return self._create_fact(content, scope)
1307:     
1308:     def feedback(self, fact_id: str, helpful: bool) -> None:
1309:         """Explicit feedback strengthens or weakens fact"""
1310:         fact = self._get_by_id(fact_id)
1311:         if fact:
1312:             fact.reinforce(success=helpful)
1313:     
1314:     def to_context(self) -> str:
1315:         """Format strong memories for system prompt"""
1316:         facts = self.recall(limit=15)
1317:         if not facts:
1318:             return ""
1319:         
1320:         lines = ["## What I Remember"]
1321:         for f in facts:
1322:             strength = "●" * int(f.weight) + "○" * (10 - int(f.weight))
1323:             lines.append(f"- [{strength}] {f.content}")
1324:         return "\n".join(lines)
1325: ```
1326: 
1327: ### Reinforcement Triggers
1328: 
1329: | Trigger | Weight Change |
1330: |---------|---------------|
1331: | Fact used, task succeeded | +0.5 to +1.0 (diminishing returns) |
1332: | Fact used, task failed | -0.5 |
1333: | User says "that's wrong" | -1.0 |
1334: | User confirms fact | +1.0 |
1335: | Day passes unused | -decay_rate × (weaker decay for strong facts) |
1336: | Weight drops below 0.5 | Excluded from context |
1337: | Weight drops below 0.1 | Archived/pruned |
1338: 
1339: ### Tools
1340: 
1341: ```python
1342: class RememberTool(Tool):
1343:     name = "remember"
1344:     description = "Store a fact for future reference"
1345:     kind = ToolKind.WRITE
1346:     
1347:     parameters = {
1348:         "type": "object",
1349:         "properties": {
1350:             "fact": {"type": "string"},
1351:             "scope": {"enum": ["project", "user"], "default": "project"},
1352:         },
1353:         "required": ["fact"]
1354:     }
1355: 
1356: class MemoryFeedbackTool(Tool):
1357:     name = "memory_feedback"
1358:     description = "Mark a remembered fact as helpful or not"
1359:     kind = ToolKind.READ
1360:     
1361:     parameters = {
1362:         "type": "object",
1363:         "properties": {
1364:             "fact_id": {"type": "string"},
1365:             "helpful": {"type": "boolean"},
1366:         },
1367:         "required": ["fact_id", "helpful"]
1368:     }
1369: ```
1370: 
1371: ### Slash Commands
1372: 
1373: ```
1374: /memory                     # Show all memories with strength visualization
1375: /memory add <fact>          # Manually add a fact
1376: /memory forget <id>         # Remove a specific fact
1377: /memory prune               # Remove all weak memories (weight < 1.0)
1378: /memory export              # Export memories to YAML
1379: /memory import <path>       # Import memories from file
1380: ```
1381: 
1382: ### REPL Visualization
1383: 
1384: ```
1385: ❯ /memory
1386: 
1387: 📚 Memory (15 facts, 3 forgotten)
1388: 
1389: Strong (weight 7+):
1390:   ●●●●●●●●○○ "API routes go in src/api/routers/" (12 uses)
1391:   ●●●●●●●○○○ "Run ./scripts/ci.sh before commits" (8 uses)
1392: 
1393: Medium (weight 3-7):
1394:   ●●●●○○○○○○ "User prefers detailed explanations" (4 uses)
1395: 
1396: Weak (weight 1-3):
1397:   ●●○○○○○○○○ "Database migrations in alembic/" (1 use, decaying)
1398: 
1399: 💀 Forgotten (weight < 1): 3 facts pruned
1400: ```
1401: 
1402: ### Acceptance Criteria
1403: 
1404: - Facts persist in YAML at project and user level
1405: - Weight increases on successful use (diminishing returns)
1406: - Weight decreases on failure or explicit negative feedback
1407: - Unused facts decay over time (Ebbinghaus curve)
1408: - Only facts above threshold appear in context
1409: - Agent can use `remember` tool to store new facts
1410: - `/memory` commands work for manual management
1411: 
1412: ---
1413: 
1414: ## Phase 12: Polish & Release
1415: 
1416: **Goal**: Production-ready release
1417: 
1418: ### Tasks
1419: 
1420: - [x] **12.1** Interactive REPL main loop (wire Agent + InputHandler + OutputRenderer)
1421: - [x] **12.2** Headless mode with `--prompt` argument
1422: - [x] **12.3** Session auto-save on graceful exit
1423: - [x] **12.4** Comprehensive test suite (>80% coverage) - Achieved 100%!
1424: - [x] **12.5** Documentation site (mkdocs)
1425: - [x] **12.6** Rebrand to henchman-ai (completed)
1426: - [x] **12.7** PyPI packaging and publishing
1427: - [x] **12.8** GitHub Actions CI/CD
1428: - [x] **12.9** Multiple theme support (in console.py)
1429: - [ ] **12.10** Performance optimization (optional)
1430: - [ ] **12.11** Error handling audit (optional)
1431: - [ ] **12.12** Security review (optional)
1432: 
1433: ### 12.6 Rename Checklist: henchman → henchman
1434: 
1435: Before PyPI publishing, rename the package from `henchman` to `henchman`:
1436: 
1437: | Item | From | To |
1438: |------|------|-----|
1439: | Package directory | `src/henchman/` | `src/henchman/` |
1440: | CLI entry point | `henchman` | `henchman` |
1441: | PyPI package name | `henchman-ai` | `henchman-ai` |
1442: | Config directories | `~/.henchman/`, `.henchman/` | `~/.henchman/`, `.henchman/` |
1443: | Context files | `HENCHMAN.md` | `HENCHMAN.md` (keep `.github/copilot-instructions.md`) |
1444: | Environment prefix | `HENCHMAN_*` | `HENCHMAN_*` |
1445: | Shell detection var | `HENCHMAN_CLI=1` | `HENCHMAN_CLI=1` |
1446: | Error base class | `MlgError` | `HenchmanError` |
1447: | Repository name | `henchman-ai` | `henchman` |
1448: 
1449: **Scrub script** (run before final commit):
1450: ```bash
1451: # Rename directories
1452: mv src/henchman src/henchman
1453: 
1454: # Update all imports and references
1455: find src tests -name "*.py" -exec sed -i 's/from henchman/from henchman/g' {} +
1456: find src tests -name "*.py" -exec sed -i 's/import henchman/import henchman/g' {} +
1457: find . -name "*.md" -exec sed -i 's/henchman-ai/henchman/g' {} +
1458: find . -name "*.md" -exec sed -i 's/MLG/HENCHMAN/g' {} +
1459: 
1460: # Update pyproject.toml
1461: sed -i 's/name = "henchman-ai"/name = "henchman"/' pyproject.toml
1462: sed -i 's/henchman = "henchman.cli.app:main"/henchman = "henchman.cli.app:main"/' pyproject.toml
1463: 
1464: # Verify no henchman references remain
1465: grep -r "henchman" src/ tests/ --include="*.py" | grep -v henchman
1466: ```
1467: 
1468: ### Completed (12.1, 12.2, 12.3, 12.4, 12.5, 12.6, 12.7, 12.8, 12.9)
1469: 
1470: **12.1 Interactive REPL Main Loop**
1471: 
1472: Created `src/henchman/cli/repl.py` with:
1473: - `ReplConfig` dataclass for REPL configuration
1474: - `Repl` class orchestrating Agent, ToolRegistry, CommandRegistry, OutputRenderer
1475: - Event-driven processing of agent responses (content, thinking, tool calls, errors)
1476: - Slash command handling (/quit, /clear, /help, /tools)
1477: - Tool execution with confirmation flow
1478: - Graceful handling of Ctrl+C and Ctrl+D
1479: 
1480: **12.2 Headless Mode**
1481: 
1482: Updated `src/henchman/cli/app.py` with:
1483: - `_get_provider()` - Provider initialization from env or settings
1484: - `_run_interactive()` - Launches REPL for interactive mode
1485: - `_run_headless()` - Processes single prompt and exits
1486: - `--prompt/-p` CLI option for headless execution
1487: - Support for text, json, and stream-json output formats
1488: 
1489: **12.3 Session Auto-Save**
1490: 
1491: Updated `src/henchman/cli/repl.py` with:
1492: - `session_manager` and `session` fields on Repl
1493: - `_auto_save_session()` method in finally block
1494: - Records user and assistant messages during conversation
1495: 
1496: **12.9 JSON Output Mode**
1497: 
1498: Created `src/henchman/cli/json_output.py` with:
1499: - `JsonOutputRenderer` class for JSON formatting
1500: - Support for `--output-format json` (single JSON object per event)
1501: - Support for `--output-format stream-json` (one JSON object per line)
1502: - Proper handling of all event types with enum to string conversion
1503: - Skips saving empty sessions
1504: - 5 new tests for auto-save functionality
1505: 
1506: **12.4 Test Coverage**
1507: 
1508: - 567+ tests passing
1509: - 100% line and branch coverage
1510: - All linting (ruff) and type checking (mypy) passing
1511: 
1512: **12.5 Documentation Site**
1513: 
1514: Created mkdocs documentation with Material theme:
1515: - `docs/index.md` - Overview and features
1516: - `docs/getting-started.md` - Installation and usage
1517: - `docs/configuration.md` - Settings reference
1518: - `docs/providers.md` - LLM provider setup
1519: - `docs/tools.md` - Built-in tools reference
1520: - `docs/mcp.md` - MCP integration guide
1521: - `docs/extensions.md` - Extension development
1522: - `docs/api.md` - API reference
1523: 
1524: **12.6 Rebrand to henchman-ai**
1525: 
1526: Completed full rebrand:
1527: - Package: `src/mlg` → `src/henchman`
1528: - CLI: `mlg` → `henchman`
1529: - Env vars: `MLG_*` → `HENCHMAN_*`
1530: - Config: `~/.mlg` → `~/.henchman`
1531: - Context: `MLG.md` → `HENCHMAN.md`
1532: 
1533: **12.7 PyPI Packaging**
1534: 
1535: - Updated pyproject.toml with classifiers
1536: - Added CHANGELOG.md
1537: - Python 3.10+ support
1538: 
1539: **12.8 GitHub Actions CI/CD**
1540: 
1541: Created workflows:
1542: - `.github/workflows/ci.yml` - lint, type-check, test, build
1543: - `.github/workflows/publish.yml` - PyPI publishing on release
1544: - `.github/workflows/docs.yml` - GitHub Pages deployment
1545: 
1546: ### Documentation
1547: 
1548: ```
1549: docs/
1550: ├── index.md           # Overview
1551: ├── getting-started.md # Quick start
1552: ├── configuration.md   # Settings reference
1553: ├── providers.md       # Provider setup
1554: ├── tools.md           # Built-in tools
1555: ├── mcp.md             # MCP integration
1556: ├── extensions.md      # Writing extensions
1557: └── api/               # API reference
1558: ```
1559: 
1560: ### CI/CD
1561: 
1562: ```yaml
1563: # .github/workflows/ci.yml
1564: - Lint (ruff)
1565: - Type check (mypy)
1566: - Test (pytest)
1567: - Build
1568: - Publish to PyPI (on tag)
1569: ```
1570: 
1571: ### Acceptance Criteria
1572: 
1573: - All tests pass
1574: - Documentation complete
1575: - Package installable from PyPI
1576: - CI/CD working
1577: 
1578: ---
1579: 
1580: ## Technical Reference
1581: 
1582: ### Async Patterns
1583: 
1584: ```python
1585: # Everything is async generators for streaming
1586: async def agent_loop() -> AsyncIterator[AgentEvent]:
1587:     async for chunk in provider.stream():
1588:         yield AgentEvent(...)
1589: 
1590: # Use anyio for runtime flexibility
1591: import anyio
1592: await anyio.sleep(1)  # Works with asyncio or trio
1593: ```
1594: 
1595: ### Error Handling
1596: 
1597: ```python
1598: # Custom exceptions
1599: class MlgError(Exception): ...
1600: class ProviderError(MlgError): ...
1601: class ToolError(MlgError): ...
1602: class ConfigError(MlgError): ...
1603: 
1604: # Graceful degradation
1605: try:
1606:     result = await tool.execute(**params)
1607: except ToolError as e:
1608:     return ToolResult(content=f"Error: {e}", success=False)
1609: ```
1610: 
1611: ### Testing Strategy
1612: 
1613: ```python
1614: # Mock providers for unit tests
1615: @pytest.fixture
1616: def mock_provider():
1617:     provider = AsyncMock(spec=ModelProvider)
1618:     async def mock_stream(*args, **kwargs):
1619:         yield StreamChunk(content="Hello")
1620:         yield StreamChunk(finish_reason=FinishReason.STOP)
1621:     provider.chat_completion_stream = mock_stream
1622:     return provider
1623: 
1624: # Integration tests with real API (optional, slow)
1625: @pytest.mark.integration
1626: async def test_deepseek_real():
1627:     provider = DeepSeekProvider()
1628:     ...
1629: ```
1630: 
1631: ---
1632: 
1633: ## Timeline Estimate
1634: 
1635: | Phase | Duration | Cumulative |
1636: |-------|----------|------------|
1637: | Phase 1: Foundation | 2 days | 2 days |
1638: | Phase 2: Providers | 3 days | 5 days |
1639: | Phase 3: Agent Loop | 3 days | 8 days |
1640: | Phase 4: Tool System | 2 days | 10 days |
1641: | Phase 5: Built-in Tools | 4 days | 14 days |
1642: | Phase 6: Configuration | 2 days | 16 days |
1643: | Phase 7: Terminal UI | 4 days | 20 days |
1644: | Phase 8: Sessions | 2 days | 22 days |
1645: | Phase 9: MCP | 3 days | 25 days |
1646: | Phase 10: Extensions | 2 days | 27 days |
1647: | Phase 11: Advanced | 5 days | 32 days |
1648: | Phase 12: Polish | 5 days | 37 days |
1649: 
1650: **Total: ~7-8 weeks** for full implementation
1651: 
1652: ---
1653: 
1654: ## Open Decisions
1655: 
1656: | Decision | Options | Recommendation |
1657: |----------|---------|----------------|
1658: | **UI Framework** | Rich only vs Textual TUI | Start with Rich, add Textual later |
1659: | **Async Runtime** | asyncio vs anyio | anyio for flexibility |
1660: | **Context Filename** | HENCHMAN.md vs AGENT.md | HENCHMAN.md (matches project) |
1661: | **Default Provider** | DeepSeek vs Ollama | DeepSeek (easy API, free tier) |
1662: 
1663: ---
1664: 
1665: *Document Version: 1.0*  
1666: *Last Updated: January 23, 2026*
```
```
