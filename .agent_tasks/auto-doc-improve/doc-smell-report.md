# Documentation Smell Report — ✅ A (Score: 92.6/100)

_Project: /home/matthew/mlg-cli_  
_Generated: 2026-02-27T14:44:27.765325+00:00_

## Executive Summary

| Metric | Value |
|:-------|------:|
| **Overall Grade** | ✅ A |
| **Overall Score** | 92.6/100 |
| **Doc Files Scanned** | 18 |
| **Source Files Checked** | 127 |
| **Total Smells** | 396 |
| **Docstring Coverage** | 100.0% |

### Smells by Severity

| Severity | Count |
|:---------|------:|
| low | 293 |
| medium | 51 |
| high | 45 |
| critical | 7 |

### Smells by Category

| Category | Count |
|:---------|------:|
| Incomplete Docstring | 333 |
| Stale Content | 33 |
| Stale Docstring | 11 |
| Consistency Error | 7 |
| Missing Docstring | 5 |
| Broken Link | 3 |
| Orphaned Page | 2 |
| Config Issue | 2 |

## 🎯 Prioritised Fix Queue

These are the highest-impact documentation smells to address first:

1. **docs/architecture.md:1** — 🔴 CRITICAL — Orphaned Page  
   'architecture.md' exists in docs/ but is not referenced in mkdocs.yml nav  
   → _Add 'architecture.md' to the nav section in mkdocs.yml, or delete the file if it's no longer needed._

2. **docs/getting-started.md:14** — 🔴 CRITICAL — Consistency Error  
   References GitHub repo 'matthew/henchman-ai' but most files reference 'mlg151/henchman-ai'. Found conflicting repos: 'matthew/henchman-ai', 'mlg151/henchman-ai'  
   → _Standardise all GitHub URLs to use 'mlg151/henchman-ai'._

3. **docs/index.md:64** — 🔴 CRITICAL — Consistency Error  
   References GitHub repo 'matthew/henchman-ai' but most files reference 'mlg151/henchman-ai'. Found conflicting repos: 'matthew/henchman-ai', 'mlg151/henchman-ai'  
   → _Standardise all GitHub URLs to use 'mlg151/henchman-ai'._

4. **docs/intelligent-context-management.md:1** — 🔴 CRITICAL — Orphaned Page  
   'intelligent-context-management.md' exists in docs/ but is not referenced in mkdocs.yml nav  
   → _Add 'intelligent-context-management.md' to the nav section in mkdocs.yml, or delete the file if it's no longer needed._

5. **mkdocs.yml:1** — 🔴 CRITICAL — Consistency Error  
   References GitHub repo 'matthew/henchman-ai' but most files reference 'mlg151/henchman-ai'. Found conflicting repos: 'matthew/henchman-ai', 'mlg151/henchman-ai'  
   → _Standardise all GitHub URLs to use 'mlg151/henchman-ai'._

6. **mkdocs.yml:1** — 🔴 CRITICAL — Consistency Error  
   References GitHub repo 'matthew/henchman-ai' but most files reference 'mlg151/henchman-ai'. Found conflicting repos: 'matthew/henchman-ai', 'mlg151/henchman-ai'  
   → _Standardise all GitHub URLs to use 'mlg151/henchman-ai'._

7. **mkdocs.yml:1** — 🔴 CRITICAL — Consistency Error  
   References GitHub repo 'matthew/henchman-ai' but most files reference 'mlg151/henchman-ai'. Found conflicting repos: 'matthew/henchman-ai', 'mlg151/henchman-ai'  
   → _Standardise all GitHub URLs to use 'mlg151/henchman-ai'._

8. **CONTRIBUTING.md:35** — 🟠 HIGH — Consistency Error  
   Contains placeholder GitHub URL 'your-username/henchman-ai.git' that should be replaced with the actual repo URL  
   → _Replace the placeholder URL with the actual project repository URL._

9. **CONTRIBUTING.md:166** — 🟠 HIGH — Stale Content  
   References 'BaseProvider' but the actual class is 'ModelProvider'  
   → _Replace 'BaseProvider' with 'ModelProvider'._

10. **CONTRIBUTING.md:174** — 🟠 HIGH — Stale Content  
   References 'BaseTool' but the actual class is 'Tool'  
   → _Replace 'BaseTool' with 'Tool'._

11. **README.md:274** — 🟠 HIGH — Broken Link  
   Link to 'docs/' resolves to 'docs' which does not exist  
   → _Fix the link target or create the missing file 'docs'._

12. **README.md:310** — 🟠 HIGH — Broken Link  
   Link to 'LICENSE' resolves to 'LICENSE' which does not exist  
   → _Fix the link target or create the missing file 'LICENSE'._

13. **docs/tools.md:1** — 🟠 HIGH — Stale Content  
   Tool 'ask_user' exists in source but is not documented in tools.md  
   → _Add a section documenting the 'ask_user' tool, including its parameters and usage._

14. **docs/tools.md:1** — 🟠 HIGH — Stale Content  
   Tool 'code_format' exists in source but is not documented in tools.md  
   → _Add a section documenting the 'code_format' tool, including its parameters and usage._

15. **docs/tools.md:1** — 🟠 HIGH — Stale Content  
   Tool 'coverage_map' exists in source but is not documented in tools.md  
   → _Add a section documenting the 'coverage_map' tool, including its parameters and usage._

16. **docs/tools.md:1** — 🟠 HIGH — Stale Content  
   Tool 'dead_code' exists in source but is not documented in tools.md  
   → _Add a section documenting the 'dead_code' tool, including its parameters and usage._

17. **docs/tools.md:1** — 🟠 HIGH — Stale Content  
   Tool 'delegate_task' exists in source but is not documented in tools.md  
   → _Add a section documenting the 'delegate_task' tool, including its parameters and usage._

18. **docs/tools.md:1** — 🟠 HIGH — Stale Content  
   Tool 'diff_view' exists in source but is not documented in tools.md  
   → _Add a section documenting the 'diff_view' tool, including its parameters and usage._

19. **docs/tools.md:1** — 🟠 HIGH — Stale Content  
   Tool 'edit_file' exists in source but is not documented in tools.md  
   → _Add a section documenting the 'edit_file' tool, including its parameters and usage._

20. **docs/tools.md:1** — 🟠 HIGH — Stale Content  
   Tool 'env_inspect' exists in source but is not documented in tools.md  
   → _Add a section documenting the 'env_inspect' tool, including its parameters and usage._


## 📊 Files Ranked by Quality

| Rank | File | Grade | Score | Smells |
|-----:|:-----|:------|------:|-------:|
| 1 | docs/tools.md | ❌ F | 0.0 | 29 |
| 2 | src/henchman/cli/console.py | ❌ F | 0.0 | 39 |
| 3 | src/henchman/cli/ui_renderer.py | ❌ F | 0.0 | 39 |
| 4 | src/henchman/cli/textual_app.py | ❌ F | 8.0 | 40 |
| 5 | src/henchman/cli/textual_widgets.py | ❌ F | 28.0 | 33 |
| 6 | mkdocs.yml | ❌ F | 33.0 | 5 |
| 7 | src/henchman/metrics/exporter.py | ❌ F | 54.0 | 7 |
| 8 | src/henchman/agents/orchestrator.py | ❌ F | 55.0 | 18 |
| 9 | CONTRIBUTING.md | 🔶 D | 68.0 | 4 |
| 10 | src/henchman/cli/output_handler.py | ⚠️ C | 74.0 | 13 |
| 11 | docs/intelligent-context-management.md | ⚠️ C | 75.0 | 2 |
| 12 | src/henchman/api/server.py | ⚠️ C | 75.0 | 8 |
| 13 | README.md | ⚠️ C | 78.0 | 3 |
| 14 | docs/architecture.md | 👍 B | 80.0 | 1 |
| 15 | docs/getting-started.md | 👍 B | 80.0 | 1 |

## 📁 Per-File Details

_Showing 25 worst files. 121 additional files omitted._

### docs/tools.md — ❌ F (0.0/100)

Words: 526 | Headings: 24 | Links: 0 | Code blocks: 15

| Line | Severity | Type | Message | Suggested Fix |
|-----:|:---------|:-----|:--------|:--------------|
| 1 | 🟠 HIGH | Stale Content | Tool 'ask_user' exists in source but is not documented in tools.md | Add a section documenting the 'ask_user' tool, including its parameters and usage. |
| 1 | 🟠 HIGH | Stale Content | Tool 'code_format' exists in source but is not documented in tools.md | Add a section documenting the 'code_format' tool, including its parameters and usage. |
| 1 | 🟠 HIGH | Stale Content | Tool 'coverage_map' exists in source but is not documented in tools.md | Add a section documenting the 'coverage_map' tool, including its parameters and usage. |
| 1 | 🟠 HIGH | Stale Content | Tool 'dead_code' exists in source but is not documented in tools.md | Add a section documenting the 'dead_code' tool, including its parameters and usage. |
| 1 | 🟠 HIGH | Stale Content | Tool 'delegate_task' exists in source but is not documented in tools.md | Add a section documenting the 'delegate_task' tool, including its parameters and usage. |
| 1 | 🟠 HIGH | Stale Content | Tool 'diff_view' exists in source but is not documented in tools.md | Add a section documenting the 'diff_view' tool, including its parameters and usage. |
| 1 | 🟠 HIGH | Stale Content | Tool 'edit_file' exists in source but is not documented in tools.md | Add a section documenting the 'edit_file' tool, including its parameters and usage. |
| 1 | 🟠 HIGH | Stale Content | Tool 'env_inspect' exists in source but is not documented in tools.md | Add a section documenting the 'env_inspect' tool, including its parameters and usage. |
| 1 | 🟠 HIGH | Stale Content | Tool 'git_ops' exists in source but is not documented in tools.md | Add a section documenting the 'git_ops' tool, including its parameters and usage. |
| 1 | 🟠 HIGH | Stale Content | Tool 'glob' exists in source but is not documented in tools.md | Add a section documenting the 'glob' tool, including its parameters and usage. |
| 1 | 🟠 HIGH | Stale Content | Tool 'grep' exists in source but is not documented in tools.md | Add a section documenting the 'grep' tool, including its parameters and usage. |
| 1 | 🟠 HIGH | Stale Content | Tool 'import_graph' exists in source but is not documented in tools.md | Add a section documenting the 'import_graph' tool, including its parameters and usage. |
| 1 | 🟠 HIGH | Stale Content | Tool 'kg_query' exists in source but is not documented in tools.md | Add a section documenting the 'kg_query' tool, including its parameters and usage. |
| 1 | 🟠 HIGH | Stale Content | Tool 'kg_update' exists in source but is not documented in tools.md | Add a section documenting the 'kg_update' tool, including its parameters and usage. |
| 1 | 🟠 HIGH | Stale Content | Tool 'lint_check' exists in source but is not documented in tools.md | Add a section documenting the 'lint_check' tool, including its parameters and usage. |

_... and 14 more smells._

### src/henchman/cli/console.py — ❌ F (0.0/100)

Public APIs: 40 | Documented: 40 | Coverage: 100.0%

| Line | Severity | Type | Message | Suggested Fix |
|-----:|:---------|:-----|:--------|:--------------|
| 558 | 🟡 MEDIUM | Incomplete Docstring | 'AsyncOutputRenderer.print' has 2 parameter(s) but no Args: section in docstring | Add an Args: section documenting: text, style |
| 562 | 🟡 MEDIUM | Incomplete Docstring | 'AsyncOutputRenderer.success' has 1 parameter(s) but no Args: section in docstring | Add an Args: section documenting: message |
| 566 | 🟡 MEDIUM | Incomplete Docstring | 'AsyncOutputRenderer.info' has 1 parameter(s) but no Args: section in docstring | Add an Args: section documenting: message |
| 570 | 🟡 MEDIUM | Incomplete Docstring | 'AsyncOutputRenderer.warning' has 1 parameter(s) but no Args: section in docstring | Add an Args: section documenting: message |
| 574 | 🟡 MEDIUM | Incomplete Docstring | 'AsyncOutputRenderer.error' has 1 parameter(s) but no Args: section in docstring | Add an Args: section documenting: message |
| 578 | 🟡 MEDIUM | Incomplete Docstring | 'AsyncOutputRenderer.markdown' has 1 parameter(s) but no Args: section in docstring | Add an Args: section documenting: content |
| 582 | 🟡 MEDIUM | Incomplete Docstring | 'AsyncOutputRenderer.code' has 2 parameter(s) but no Args: section in docstring | Add an Args: section documenting: code, language |
| 586 | 🟡 MEDIUM | Incomplete Docstring | 'AsyncOutputRenderer.table' has 2 parameter(s) but no Args: section in docstring | Add an Args: section documenting: data, title |
| 590 | 🟡 MEDIUM | Incomplete Docstring | 'AsyncOutputRenderer.diff' has 3 parameter(s) but no Args: section in docstring | Add an Args: section documenting: old, new, filename |
| 180 | 🟢 LOW | Incomplete Docstring | 'ThemeManager.set_theme' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'ThemeManager.set_theme'. |
| 196 | 🟢 LOW | Incomplete Docstring | 'ThemeManager.register_theme' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'ThemeManager.register_theme'. |
| 262 | 🟢 LOW | Incomplete Docstring | 'OutputRenderer.print' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'OutputRenderer.print'. |
| 271 | 🟢 LOW | Incomplete Docstring | 'OutputRenderer.success' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'OutputRenderer.success'. |
| 280 | 🟢 LOW | Incomplete Docstring | 'OutputRenderer.info' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'OutputRenderer.info'. |
| 289 | 🟢 LOW | Incomplete Docstring | 'OutputRenderer.warning' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'OutputRenderer.warning'. |

_... and 24 more smells._

### src/henchman/cli/ui_renderer.py — ❌ F (0.0/100)

Public APIs: 35 | Documented: 35 | Coverage: 100.0%

| Line | Severity | Type | Message | Suggested Fix |
|-----:|:---------|:-----|:--------|:--------------|
| 266 | 🟡 MEDIUM | Incomplete Docstring | 'UIRenderer.success' has 1 parameter(s) but no Args: section in docstring | Add an Args: section documenting: message |
| 270 | 🟡 MEDIUM | Incomplete Docstring | 'UIRenderer.info' has 1 parameter(s) but no Args: section in docstring | Add an Args: section documenting: message |
| 274 | 🟡 MEDIUM | Incomplete Docstring | 'UIRenderer.warning' has 1 parameter(s) but no Args: section in docstring | Add an Args: section documenting: message |
| 278 | 🟡 MEDIUM | Incomplete Docstring | 'UIRenderer.error' has 1 parameter(s) but no Args: section in docstring | Add an Args: section documenting: message |
| 282 | 🟡 MEDIUM | Incomplete Docstring | 'UIRenderer.muted' has 1 parameter(s) but no Args: section in docstring | Add an Args: section documenting: text |
| 286 | 🟡 MEDIUM | Incomplete Docstring | 'UIRenderer.heading' has 1 parameter(s) but no Args: section in docstring | Add an Args: section documenting: text |
| 290 | 🟡 MEDIUM | Incomplete Docstring | 'UIRenderer.markdown' has 1 parameter(s) but no Args: section in docstring | Add an Args: section documenting: content |
| 294 | 🟡 MEDIUM | Incomplete Docstring | 'UIRenderer.code' has 2 parameter(s) but no Args: section in docstring | Add an Args: section documenting: code, language |
| 298 | 🟡 MEDIUM | Incomplete Docstring | 'UIRenderer.rule' has 1 parameter(s) but no Args: section in docstring | Add an Args: section documenting: title |
| 306 | 🟡 MEDIUM | Incomplete Docstring | 'UIRenderer.tool_call' has 2 parameter(s) but no Args: section in docstring | Add an Args: section documenting: name, arguments |
| 310 | 🟡 MEDIUM | Incomplete Docstring | 'UIRenderer.tool_result' has 3 parameter(s) but no Args: section in docstring | Add an Args: section documenting: content, success, error |
| 314 | 🟡 MEDIUM | Incomplete Docstring | 'UIRenderer.tool_summary' has 2 parameter(s) but no Args: section in docstring | Add an Args: section documenting: name, duration |
| 318 | 🟡 MEDIUM | Incomplete Docstring | 'UIRenderer.agent_content' has 1 parameter(s) but no Args: section in docstring | Add an Args: section documenting: content |
| 69 | 🟢 LOW | Incomplete Docstring | 'ProgressManager.update_task' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'ProgressManager.update_task'. |
| 84 | 🟢 LOW | Incomplete Docstring | 'ProgressManager.complete_task' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'ProgressManager.complete_task'. |

_... and 24 more smells._

### src/henchman/cli/textual_app.py — ❌ F (8.0/100)

Public APIs: 45 | Documented: 45 | Coverage: 100.0%

| Line | Severity | Type | Message | Suggested Fix |
|-----:|:---------|:-----|:--------|:--------------|
| 418 | 🟡 MEDIUM | Incomplete Docstring | 'HenchmanTextualApp.orchestrator' has 1 parameter(s) but no Args: section in docstring | Add an Args: section documenting: value |
| 433 | 🟡 MEDIUM | Incomplete Docstring | 'HenchmanTextualApp.tool_registry' has 1 parameter(s) but no Args: section in docstring | Add an Args: section documenting: value |
| 448 | 🟡 MEDIUM | Incomplete Docstring | 'HenchmanTextualApp.session_manager' has 1 parameter(s) but no Args: section in docstring | Add an Args: section documenting: value |
| 463 | 🟡 MEDIUM | Incomplete Docstring | 'HenchmanTextualApp.agent' has 1 parameter(s) but no Args: section in docstring | Add an Args: section documenting: value |
| 418 | 🟢 LOW | Incomplete Docstring | 'HenchmanTextualApp.orchestrator' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'HenchmanTextualApp.orchestrator'. |
| 433 | 🟢 LOW | Incomplete Docstring | 'HenchmanTextualApp.tool_registry' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'HenchmanTextualApp.tool_registry'. |
| 448 | 🟢 LOW | Incomplete Docstring | 'HenchmanTextualApp.session_manager' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'HenchmanTextualApp.session_manager'. |
| 463 | 🟢 LOW | Incomplete Docstring | 'HenchmanTextualApp.agent' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'HenchmanTextualApp.agent'. |
| 519 | 🟢 LOW | Incomplete Docstring | 'HenchmanTextualApp.on_mount' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'HenchmanTextualApp.on_mount'. |
| 534 | 🟢 LOW | Incomplete Docstring | 'HenchmanTextualApp.on_unmount' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'HenchmanTextualApp.on_unmount'. |
| 803 | 🟢 LOW | Incomplete Docstring | 'HenchmanTextualApp.action_submit_message' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'HenchmanTextualApp.action_submit_message'. |
| 866 | 🟢 LOW | Incomplete Docstring | 'HenchmanTextualApp.process_user_input' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'HenchmanTextualApp.process_user_input'. |
| 972 | 🟢 LOW | Incomplete Docstring | 'HenchmanTextualApp.on_agent_content_message' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'HenchmanTextualApp.on_agent_content_message'. |
| 982 | 🟢 LOW | Incomplete Docstring | 'HenchmanTextualApp.on_agent_thought_message' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'HenchmanTextualApp.on_agent_thought_message'. |
| 1003 | 🟢 LOW | Incomplete Docstring | 'HenchmanTextualApp.on_tool_call_request_message' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'HenchmanTextualApp.on_tool_call_request_message'. |

_... and 25 more smells._

### src/henchman/cli/textual_widgets.py — ❌ F (28.0/100)

Public APIs: 54 | Documented: 54 | Coverage: 100.0%

| Line | Severity | Type | Message | Suggested Fix |
|-----:|:---------|:-----|:--------|:--------------|
| 397 | 🟡 MEDIUM | Incomplete Docstring | 'ThinkingMessage.content' has 1 parameter(s) but no Args: section in docstring | Add an Args: section documenting: value |
| 606 | 🟡 MEDIUM | Incomplete Docstring | 'ToolMessage.content' has 1 parameter(s) but no Args: section in docstring | Add an Args: section documenting: value |
| 147 | 🟢 LOW | Incomplete Docstring | 'HenchmanTextArea.on_key' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'HenchmanTextArea.on_key'. |
| 167 | 🟢 LOW | Incomplete Docstring | 'HenchmanTextArea.action_newline' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'HenchmanTextArea.action_newline'. |
| 171 | 🟢 LOW | Incomplete Docstring | 'HenchmanTextArea.action_history_up' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'HenchmanTextArea.action_history_up'. |
| 182 | 🟢 LOW | Incomplete Docstring | 'HenchmanTextArea.action_history_down' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'HenchmanTextArea.action_history_down'. |
| 258 | 🟢 LOW | Incomplete Docstring | 'ChatMessage.set_highlight' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'ChatMessage.set_highlight'. |
| 271 | 🟢 LOW | Incomplete Docstring | 'ChatMessage.finalize_as_markdown' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'ChatMessage.finalize_as_markdown'. |
| 283 | 🟢 LOW | Incomplete Docstring | 'ChatMessage.append' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'ChatMessage.append'. |
| 294 | 🟢 LOW | Incomplete Docstring | 'ChatMessage.set_content' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'ChatMessage.set_content'. |
| 397 | 🟢 LOW | Incomplete Docstring | 'ThinkingMessage.content' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'ThinkingMessage.content'. |
| 457 | 🟢 LOW | Incomplete Docstring | 'ThinkingMessage.toggle_expansion' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'ThinkingMessage.toggle_expansion'. |
| 465 | 🟢 LOW | Incomplete Docstring | 'ThinkingMessage.on_click' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'ThinkingMessage.on_click'. |
| 473 | 🟢 LOW | Incomplete Docstring | 'ThinkingMessage.set_highlight' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'ThinkingMessage.set_highlight'. |
| 482 | 🟢 LOW | Incomplete Docstring | 'ThinkingMessage.append' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'ThinkingMessage.append'. |

_... and 18 more smells._

### mkdocs.yml — ❌ F (33.0/100)

| Line | Severity | Type | Message | Suggested Fix |
|-----:|:---------|:-----|:--------|:--------------|
| 1 | 🔴 CRITICAL | Consistency Error | References GitHub repo 'matthew/henchman-ai' but most files reference 'mlg151/henchman-ai'. Found conflicting repos: 'matthew/henchman-ai', 'mlg151/henchman-ai' | Standardise all GitHub URLs to use 'mlg151/henchman-ai'. |
| 1 | 🔴 CRITICAL | Consistency Error | References GitHub repo 'matthew/henchman-ai' but most files reference 'mlg151/henchman-ai'. Found conflicting repos: 'matthew/henchman-ai', 'mlg151/henchman-ai' | Standardise all GitHub URLs to use 'mlg151/henchman-ai'. |
| 1 | 🔴 CRITICAL | Consistency Error | References GitHub repo 'matthew/henchman-ai' but most files reference 'mlg151/henchman-ai'. Found conflicting repos: 'matthew/henchman-ai', 'mlg151/henchman-ai' | Standardise all GitHub URLs to use 'mlg151/henchman-ai'. |
| 1 | 🟡 MEDIUM | Config Issue | Markdown files contain ```mermaid blocks but pymdownx.superfences is not configured with mermaid custom fences — diagrams won't render | Add custom_fences mermaid configuration to pymdownx.superfences in mkdocs.yml, or install mkdocs-mermaid2-plugin. |
| 1 | 🟢 LOW | Config Issue | docs/api.md exists but mkdocstrings plugin is not configured — API docs are hand-written and will drift from source code | Add mkdocstrings plugin to mkdocs.yml to auto-generate API docs from docstrings. |

### src/henchman/metrics/exporter.py — ❌ F (54.0/100)

Public APIs: 6 | Documented: 6 | Coverage: 100.0%

| Line | Severity | Type | Message | Suggested Fix |
|-----:|:---------|:-----|:--------|:--------------|
| 29 | 🟠 HIGH | Stale Docstring | 'MetricsExporter.export_to_json' has undocumented parameters: filters | Add these parameters to the Args: section: filters |
| 78 | 🟠 HIGH | Stale Docstring | 'MetricsExporter.export_to_csv' has undocumented parameters: filters | Add these parameters to the Args: section: filters |
| 91 | 🟠 HIGH | Stale Docstring | 'MetricsExporter.export_to_prometheus' has undocumented parameters: filters | Add these parameters to the Args: section: filters |
| 104 | 🟠 HIGH | Stale Docstring | 'MetricsExporter.export_summary' has undocumented parameters: filters | Add these parameters to the Args: section: filters |
| 29 | 🟢 LOW | Incomplete Docstring | 'MetricsExporter.export_to_json' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'MetricsExporter.export_to_json'. |
| 78 | 🟢 LOW | Incomplete Docstring | 'MetricsExporter.export_to_csv' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'MetricsExporter.export_to_csv'. |
| 91 | 🟢 LOW | Incomplete Docstring | 'MetricsExporter.export_to_prometheus' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'MetricsExporter.export_to_prometheus'. |

### src/henchman/agents/orchestrator.py — ❌ F (55.0/100)

Public APIs: 30 | Documented: 30 | Coverage: 100.0%

| Line | Severity | Type | Message | Suggested Fix |
|-----:|:---------|:-----|:--------|:--------------|
| 253 | 🟡 MEDIUM | Incomplete Docstring | 'PerformanceMetrics.track_file_access' has 1 parameter(s) but no Args: section in docstring | Add an Args: section documenting: file_path |
| 257 | 🟡 MEDIUM | Incomplete Docstring | 'PerformanceMetrics.track_tool_usage' has 1 parameter(s) but no Args: section in docstring | Add an Args: section documenting: tool_name |
| 314 | 🟡 MEDIUM | Incomplete Docstring | 'ToolMetrics.track_tool_call' has 2 parameter(s) but no Args: section in docstring | Add an Args: section documenting: tool_name, success |
| 233 | 🟢 LOW | Incomplete Docstring | 'PerformanceMetrics.reset' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'PerformanceMetrics.reset'. |
| 245 | 🟢 LOW | Incomplete Docstring | 'PerformanceMetrics.calculate_file_re_reads' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'PerformanceMetrics.calculate_file_re_reads'. |
| 253 | 🟢 LOW | Incomplete Docstring | 'PerformanceMetrics.track_file_access' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'PerformanceMetrics.track_file_access'. |
| 257 | 🟢 LOW | Incomplete Docstring | 'PerformanceMetrics.track_tool_usage' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'PerformanceMetrics.track_tool_usage'. |
| 272 | 🟢 LOW | Incomplete Docstring | 'QualityMetrics.reset' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'QualityMetrics.reset'. |
| 279 | 🟢 LOW | Incomplete Docstring | 'QualityMetrics.calculate_test_percentage' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'QualityMetrics.calculate_test_percentage'. |
| 302 | 🟢 LOW | Incomplete Docstring | 'ToolMetrics.reset' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'ToolMetrics.reset'. |
| 314 | 🟢 LOW | Incomplete Docstring | 'ToolMetrics.track_tool_call' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'ToolMetrics.track_tool_call'. |
| 338 | 🟢 LOW | Incomplete Docstring | 'ToolMetrics.calculate_error_rate' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'ToolMetrics.calculate_error_rate'. |
| 381 | 🟢 LOW | Incomplete Docstring | 'OrchestratorMetrics.reset_for_run' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'OrchestratorMetrics.reset_for_run'. |
| 392 | 🟢 LOW | Incomplete Docstring | 'OrchestratorMetrics.calculate_final_metrics' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'OrchestratorMetrics.calculate_final_metrics'. |
| 414 | 🟢 LOW | Incomplete Docstring | 'OrchestratorMetrics.to_dict' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'OrchestratorMetrics.to_dict'. |

_... and 3 more smells._

### CONTRIBUTING.md — 🔶 D (68.0/100)

Words: 763 | Headings: 41 | Links: 7 | Code blocks: 7

| Line | Severity | Type | Message | Suggested Fix |
|-----:|:---------|:-----|:--------|:--------------|
| 35 | 🟠 HIGH | Consistency Error | Contains placeholder GitHub URL 'your-username/henchman-ai.git' that should be replaced with the actual repo URL | Replace the placeholder URL with the actual project repository URL. |
| 166 | 🟠 HIGH | Stale Content | References 'BaseProvider' but the actual class is 'ModelProvider' | Replace 'BaseProvider' with 'ModelProvider'. |
| 174 | 🟠 HIGH | Stale Content | References 'BaseTool' but the actual class is 'Tool' | Replace 'BaseTool' with 'Tool'. |
| 101 | 🟢 LOW | Stale Content | Hardcoded line count '50 lines' may become stale as the codebase evolves | Remove the specific line count or replace with a relative description (e.g. 'compact', 'concise'). |

### src/henchman/cli/output_handler.py — ⚠️ C (74.0/100)

Public APIs: 18 | Documented: 18 | Coverage: 100.0%

| Line | Severity | Type | Message | Suggested Fix |
|-----:|:---------|:-----|:--------|:--------------|
| 238 | 🟢 LOW | Incomplete Docstring | 'OutputHandler.print_welcome' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'OutputHandler.print_welcome'. |
| 242 | 🟢 LOW | Incomplete Docstring | 'OutputHandler.print_goodbye' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'OutputHandler.print_goodbye'. |
| 246 | 🟢 LOW | Incomplete Docstring | 'OutputHandler.print_newline' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'OutputHandler.print_newline'. |
| 250 | 🟢 LOW | Incomplete Docstring | 'OutputHandler.success' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'OutputHandler.success'. |
| 258 | 🟢 LOW | Incomplete Docstring | 'OutputHandler.error' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'OutputHandler.error'. |
| 266 | 🟢 LOW | Incomplete Docstring | 'OutputHandler.warning' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'OutputHandler.warning'. |
| 274 | 🟢 LOW | Incomplete Docstring | 'OutputHandler.muted' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'OutputHandler.muted'. |
| 282 | 🟢 LOW | Incomplete Docstring | 'OutputHandler.thinking' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'OutputHandler.thinking'. |
| 290 | 🟢 LOW | Incomplete Docstring | 'OutputHandler.print_agent_content' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'OutputHandler.print_agent_content'. |
| 310 | 🟢 LOW | Incomplete Docstring | 'OutputHandler.show_turn_status' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'OutputHandler.show_turn_status'. |
| 345 | 🟢 LOW | Incomplete Docstring | 'OutputHandler.update_task' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'OutputHandler.update_task'. |
| 355 | 🟢 LOW | Incomplete Docstring | 'OutputHandler.complete_task' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'OutputHandler.complete_task'. |
| 363 | 🟢 LOW | Incomplete Docstring | 'OutputHandler.start_background_indexing' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'OutputHandler.start_background_indexing'. |

### docs/intelligent-context-management.md — ⚠️ C (75.0/100)

Words: 1726 | Headings: 67 | Links: 4 | Code blocks: 27

| Line | Severity | Type | Message | Suggested Fix |
|-----:|:---------|:-----|:--------|:--------------|
| 1 | 🔴 CRITICAL | Orphaned Page | 'intelligent-context-management.md' exists in docs/ but is not referenced in mkdocs.yml nav | Add 'intelligent-context-management.md' to the nav section in mkdocs.yml, or delete the file if it's no longer needed. |
| 474 | 🟡 MEDIUM | Broken Link | Link to 'configuration.md#performance-tuning' — file exists but anchor '#performance-tuning' not found | Verify the heading exists in 'docs/configuration.md' or fix the fragment. |

### src/henchman/api/server.py — ⚠️ C (75.0/100)

Public APIs: 7 | Documented: 7 | Coverage: 100.0%

| Line | Severity | Type | Message | Suggested Fix |
|-----:|:---------|:-----|:--------|:--------------|
| 75 | 🟡 MEDIUM | Incomplete Docstring | 'lifespan' has 1 parameter(s) but no Args: section in docstring | Add an Args: section documenting: _app |
| 148 | 🟡 MEDIUM | Incomplete Docstring | 'http_exception_handler' has 2 parameter(s) but no Args: section in docstring | Add an Args: section documenting: request, exc |
| 161 | 🟡 MEDIUM | Incomplete Docstring | 'generic_exception_handler' has 2 parameter(s) but no Args: section in docstring | Add an Args: section documenting: request, _exc |
| 75 | 🟢 LOW | Incomplete Docstring | 'lifespan' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'lifespan'. |
| 138 | 🟢 LOW | Incomplete Docstring | 'root' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'root'. |
| 148 | 🟢 LOW | Incomplete Docstring | 'http_exception_handler' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'http_exception_handler'. |
| 161 | 🟢 LOW | Incomplete Docstring | 'generic_exception_handler' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'generic_exception_handler'. |
| 173 | 🟢 LOW | Incomplete Docstring | 'run_server' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'run_server'. |

### README.md — ⚠️ C (78.0/100)

Words: 1142 | Headings: 58 | Links: 17 | Code blocks: 16

| Line | Severity | Type | Message | Suggested Fix |
|-----:|:---------|:-----|:--------|:--------------|
| 274 | 🟠 HIGH | Broken Link | Link to 'docs/' resolves to 'docs' which does not exist | Fix the link target or create the missing file 'docs'. |
| 310 | 🟠 HIGH | Broken Link | Link to 'LICENSE' resolves to 'LICENSE' which does not exist | Fix the link target or create the missing file 'LICENSE'. |
| 85 | 🟢 LOW | Stale Content | Hardcoded line count '406 lines' may become stale as the codebase evolves | Remove the specific line count or replace with a relative description (e.g. 'compact', 'concise'). |

### docs/architecture.md — 👍 B (80.0/100)

Words: 968 | Headings: 24 | Links: 4 | Code blocks: 5

| Line | Severity | Type | Message | Suggested Fix |
|-----:|:---------|:-----|:--------|:--------------|
| 1 | 🔴 CRITICAL | Orphaned Page | 'architecture.md' exists in docs/ but is not referenced in mkdocs.yml nav | Add 'architecture.md' to the nav section in mkdocs.yml, or delete the file if it's no longer needed. |

### docs/getting-started.md — 👍 B (80.0/100)

Words: 266 | Headings: 16 | Links: 3 | Code blocks: 11

| Line | Severity | Type | Message | Suggested Fix |
|-----:|:---------|:-----|:--------|:--------------|
| 14 | 🔴 CRITICAL | Consistency Error | References GitHub repo 'matthew/henchman-ai' but most files reference 'mlg151/henchman-ai'. Found conflicting repos: 'matthew/henchman-ai', 'mlg151/henchman-ai' | Standardise all GitHub URLs to use 'mlg151/henchman-ai'. |

### docs/index.md — 👍 B (80.0/100)

Words: 292 | Headings: 11 | Links: 8 | Code blocks: 1

| Line | Severity | Type | Message | Suggested Fix |
|-----:|:---------|:-----|:--------|:--------------|
| 64 | 🔴 CRITICAL | Consistency Error | References GitHub repo 'matthew/henchman-ai' but most files reference 'mlg151/henchman-ai'. Found conflicting repos: 'matthew/henchman-ai', 'mlg151/henchman-ai' | Standardise all GitHub URLs to use 'mlg151/henchman-ai'. |

### src/henchman/api/endpoints/health.py — 👍 B (80.0/100)

Public APIs: 6 | Documented: 6 | Coverage: 100.0%

| Line | Severity | Type | Message | Suggested Fix |
|-----:|:---------|:-----|:--------|:--------------|
| 59 | 🟠 HIGH | Stale Docstring | 'get_metrics' has undocumented parameters: _api_key | Add these parameters to the Args: section: _api_key |
| 111 | 🟠 HIGH | Stale Docstring | 'get_usage' has undocumented parameters: _api_key | Add these parameters to the Args: section: _api_key |

### src/henchman/core/agent.py — 👍 B (82.0/100)

Public APIs: 9 | Documented: 9 | Coverage: 100.0%

| Line | Severity | Type | Message | Suggested Fix |
|-----:|:---------|:-----|:--------|:--------------|
| 646 | 🟡 MEDIUM | Incomplete Docstring | 'Agent.run' has 1 parameter(s) but no Args: section in docstring | Add an Args: section documenting: user_input |
| 715 | 🟡 MEDIUM | Incomplete Docstring | 'Agent.submit_tool_result' has 2 parameter(s) but no Args: section in docstring | Add an Args: section documenting: tool_call_id, result |
| 168 | 🟢 LOW | Incomplete Docstring | 'Agent.clear_history' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'Agent.clear_history'. |
| 646 | 🟢 LOW | Incomplete Docstring | 'Agent.run' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'Agent.run'. |
| 715 | 🟢 LOW | Incomplete Docstring | 'Agent.submit_tool_result' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'Agent.submit_tool_result'. |
| 719 | 🟢 LOW | Incomplete Docstring | 'Agent.continue_with_tool_results' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'Agent.continue_with_tool_results'. |

### src/henchman/core/session.py — 👍 B (83.0/100)

Public APIs: 34 | Documented: 34 | Coverage: 100.0%

| Line | Severity | Type | Message | Suggested Fix |
|-----:|:---------|:-----|:--------|:--------------|
| 169 | 🟡 MEDIUM | Incomplete Docstring | 'TurnSummaryRecord.from_dict' has 1 parameter(s) but no Args: section in docstring | Add an Args: section documenting: data |
| 158 | 🟢 LOW | Incomplete Docstring | 'TurnSummaryRecord.to_dict' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'TurnSummaryRecord.to_dict'. |
| 169 | 🟢 LOW | Incomplete Docstring | 'TurnSummaryRecord.from_dict' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'TurnSummaryRecord.from_dict'. |
| 328 | 🟢 LOW | Incomplete Docstring | 'SessionManager.set_current' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'SessionManager.set_current'. |
| 336 | 🟢 LOW | Incomplete Docstring | 'SessionManager.clear_current' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'SessionManager.clear_current'. |
| 474 | 🟢 LOW | Incomplete Docstring | 'SessionManager.delete' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'SessionManager.delete'. |
| 911 | 🟢 LOW | Incomplete Docstring | 'SessionManager.delete_template' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'SessionManager.delete_template'. |

### src/henchman/utils/validation.py — 👍 B (83.0/100)

Public APIs: 4 | Documented: 4 | Coverage: 100.0%

| Line | Severity | Type | Message | Suggested Fix |
|-----:|:---------|:-----|:--------|:--------------|
| 12 | 🟡 MEDIUM | Incomplete Docstring | 'validate_message_sequence' has 1 parameter(s) but no Args: section in docstring | Add an Args: section documenting: messages |
| 179 | 🟡 MEDIUM | Incomplete Docstring | 'is_valid_message_sequence' has 1 parameter(s) but no Args: section in docstring | Add an Args: section documenting: messages |
| 192 | 🟡 MEDIUM | Incomplete Docstring | 'format_message_sequence_for_debug' has 1 parameter(s) but no Args: section in docstring | Add an Args: section documenting: messages |
| 12 | 🟢 LOW | Incomplete Docstring | 'validate_message_sequence' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'validate_message_sequence'. |

### src/henchman/cli/app.py — 👍 B (84.0/100)

Public APIs: 3 | Documented: 3 | Coverage: 100.0%

| Line | Severity | Type | Message | Suggested Fix |
|-----:|:---------|:-----|:--------|:--------------|
| 599 | 🟡 MEDIUM | Incomplete Docstring | 'cli' has 1 parameter(s) but no Args: section in docstring | Add an Args: section documenting: ctx |
| 644 | 🟡 MEDIUM | Incomplete Docstring | 'chat_command' has 8 parameter(s) but no Args: section in docstring | Add an Args: section documenting: prompt, agent, team, output_format, plan, yes, tui, debug |
| 599 | 🟢 LOW | Incomplete Docstring | 'cli' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'cli'. |
| 644 | 🟢 LOW | Incomplete Docstring | 'chat_command' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'chat_command'. |
| 693 | 🟢 LOW | Incomplete Docstring | 'main' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'main'. |

### src/henchman/cli/textual_screens.py — 👍 B (86.0/100)

Public APIs: 15 | Documented: 15 | Coverage: 100.0%

| Line | Severity | Type | Message | Suggested Fix |
|-----:|:---------|:-----|:--------|:--------------|
| 154 | 🟢 LOW | Incomplete Docstring | 'ConfirmToolScreen.on_button_pressed' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'ConfirmToolScreen.on_button_pressed'. |
| 162 | 🟢 LOW | Incomplete Docstring | 'ConfirmToolScreen.action_approve' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'ConfirmToolScreen.action_approve'. |
| 166 | 🟢 LOW | Incomplete Docstring | 'ConfirmToolScreen.action_deny' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'ConfirmToolScreen.action_deny'. |
| 228 | 🟢 LOW | Incomplete Docstring | 'HelpScreen.on_button_pressed' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'HelpScreen.on_button_pressed'. |
| 343 | 🟢 LOW | Incomplete Docstring | 'ProviderScreen.on_button_pressed' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'ProviderScreen.on_button_pressed'. |
| 450 | 🟢 LOW | Incomplete Docstring | 'SessionScreen.on_button_pressed' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'SessionScreen.on_button_pressed'. |
| 468 | 🟢 LOW | Incomplete Docstring | 'SessionScreen.action_cancel' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'SessionScreen.action_cancel'. |

### src/henchman/knowledge/store.py — 👍 B (86.0/100)

Public APIs: 23 | Documented: 23 | Coverage: 100.0%

| Line | Severity | Type | Message | Suggested Fix |
|-----:|:---------|:-----|:--------|:--------------|
| 144 | 🟢 LOW | Incomplete Docstring | 'KnowledgeStore.load' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'KnowledgeStore.load'. |
| 164 | 🟢 LOW | Incomplete Docstring | 'KnowledgeStore.save' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'KnowledgeStore.save'. |
| 179 | 🟢 LOW | Incomplete Docstring | 'KnowledgeStore.add_entity' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'KnowledgeStore.add_entity'. |
| 294 | 🟢 LOW | Incomplete Docstring | 'KnowledgeStore.add_relation' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'KnowledgeStore.add_relation'. |
| 442 | 🟢 LOW | Incomplete Docstring | 'KnowledgeStore.entity_count' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'KnowledgeStore.entity_count'. |
| 446 | 🟢 LOW | Incomplete Docstring | 'KnowledgeStore.relation_count' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'KnowledgeStore.relation_count'. |
| 450 | 🟢 LOW | Incomplete Docstring | 'KnowledgeStore.clear' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'KnowledgeStore.clear'. |

### src/henchman/tools/registry.py — 👍 B (86.0/100)

Public APIs: 15 | Documented: 15 | Coverage: 100.0%

| Line | Severity | Type | Message | Suggested Fix |
|-----:|:---------|:-----|:--------|:--------------|
| 63 | 🟢 LOW | Incomplete Docstring | 'ToolRegistry.set_retry_config' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'ToolRegistry.set_retry_config'. |
| 71 | 🟢 LOW | Incomplete Docstring | 'ToolRegistry.set_plan_mode' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'ToolRegistry.set_plan_mode'. |
| 79 | 🟢 LOW | Incomplete Docstring | 'ToolRegistry.register' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'ToolRegistry.register'. |
| 93 | 🟢 LOW | Incomplete Docstring | 'ToolRegistry.unregister' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'ToolRegistry.unregister'. |
| 137 | 🟢 LOW | Incomplete Docstring | 'ToolRegistry.set_confirmation_handler' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'ToolRegistry.set_confirmation_handler'. |
| 146 | 🟢 LOW | Incomplete Docstring | 'ToolRegistry.add_auto_approve_policy' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'ToolRegistry.add_auto_approve_policy'. |
| 157 | 🟢 LOW | Incomplete Docstring | 'ToolRegistry.remove_auto_approve_policy' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'ToolRegistry.remove_auto_approve_policy'. |

### src/henchman/cli/session_manager.py — 👍 B (88.0/100)

Public APIs: 14 | Documented: 14 | Coverage: 100.0%

| Line | Severity | Type | Message | Suggested Fix |
|-----:|:---------|:-----|:--------|:--------------|
| 54 | 🟢 LOW | Incomplete Docstring | 'ReplSessionManager.set_session' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'ReplSessionManager.set_session'. |
| 99 | 🟢 LOW | Incomplete Docstring | 'ReplSessionManager.auto_save_session' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'ReplSessionManager.auto_save_session'. |
| 188 | 🟢 LOW | Incomplete Docstring | 'ReplSessionManager.delete' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'ReplSessionManager.delete'. |
| 210 | 🟢 LOW | Incomplete Docstring | 'ReplSessionManager.record_user_message' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'ReplSessionManager.record_user_message'. |
| 219 | 🟢 LOW | Incomplete Docstring | 'ReplSessionManager.record_agent_message' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'ReplSessionManager.record_agent_message'. |
| 242 | 🟢 LOW | Incomplete Docstring | 'ReplSessionManager.record_tool_result' returns a value but has no Returns: or Yields: section | Add a Returns: section describing the return value of 'ReplSessionManager.record_tool_result'. |

## ✨ Clean Files (69 files with no smells)

<details><summary>Click to expand</summary>

- CHANGELOG.md — ✅ A
- RELEASE_CHECKLIST.md — ✅ A
- docs/agents.md — ✅ A
- docs/api.md — ✅ A
- docs/configuration.md — ✅ A
- docs/extensions.md — ✅ A
- docs/mcp.md — ✅ A
- docs/providers.md — ✅ A
- evals/README.md — ✅ A
- tests/ui_integration/INTERACTIVE_SESSION_TESTS.md — ✅ A
- src/henchman/agents/delegation_manager.py — ✅ A
- src/henchman/agents/presets.py — ✅ A
- src/henchman/agents/prompts.py — ✅ A
- src/henchman/api/auth.py — ✅ A
- src/henchman/api/endpoints/chat.py — ✅ A
- src/henchman/api/state.py — ✅ A
- src/henchman/cli/command_processor.py — ✅ A
- src/henchman/cli/textual_messages.py — ✅ A
- src/henchman/config/context.py — ✅ A
- src/henchman/config/environment.py — ✅ A
- src/henchman/config/schema.py — ✅ A
- src/henchman/core/events.py — ✅ A
- src/henchman/extensions/base.py — ✅ A
- src/henchman/extensions/models.py — ✅ A
- src/henchman/knowledge/models.py — ✅ A
- src/henchman/knowledge/scanner.py — ✅ A
- src/henchman/mcp/config.py — ✅ A
- src/henchman/metrics/models.py — ✅ A
- src/henchman/providers/anthropic.py — ✅ A
- src/henchman/providers/base.py — ✅ A
- src/henchman/providers/deepseek.py — ✅ A
- src/henchman/providers/ollama.py — ✅ A
- src/henchman/providers/openai_compat.py — ✅ A
- src/henchman/providers/openrouter.py — ✅ A
- src/henchman/providers/utils.py — ✅ A
- src/henchman/rag/chunker.py — ✅ A
- src/henchman/rag/embedder.py — ✅ A
- src/henchman/rag/repo_id.py — ✅ A
- src/henchman/tools/builtins/code_format.py — ✅ A
- src/henchman/tools/builtins/coverage_map.py — ✅ A
- src/henchman/tools/builtins/dead_code.py — ✅ A
- src/henchman/tools/builtins/delegate.py — ✅ A
- src/henchman/tools/builtins/diff_view.py — ✅ A
- src/henchman/tools/builtins/env_inspect.py — ✅ A
- src/henchman/tools/builtins/file_edit.py — ✅ A
- src/henchman/tools/builtins/file_read.py — ✅ A
- src/henchman/tools/builtins/file_write.py — ✅ A
- src/henchman/tools/builtins/git_ops.py — ✅ A
- src/henchman/tools/builtins/glob_tool.py — ✅ A
- src/henchman/tools/builtins/grep.py — ✅ A
- src/henchman/tools/builtins/import_graph.py — ✅ A
- src/henchman/tools/builtins/lint_check.py — ✅ A
- src/henchman/tools/builtins/ls.py — ✅ A
- src/henchman/tools/builtins/patch_apply.py — ✅ A
- src/henchman/tools/builtins/pip_inspect.py — ✅ A
- src/henchman/tools/builtins/pytest_run.py — ✅ A
- src/henchman/tools/builtins/python_ast.py — ✅ A
- src/henchman/tools/builtins/python_exec.py — ✅ A
- src/henchman/tools/builtins/rag_search.py — ✅ A
- src/henchman/tools/builtins/shell.py — ✅ A
- src/henchman/tools/builtins/test_gen.py — ✅ A
- src/henchman/tools/builtins/traceback_parse.py — ✅ A
- src/henchman/tools/builtins/web_fetch.py — ✅ A
- src/henchman/tools/builtins/web_search.py — ✅ A
- src/henchman/utils/compaction.py — ✅ A
- src/henchman/utils/intelligent_context.py — ✅ A
- src/henchman/utils/lazy_import.py — ✅ A
- src/henchman/utils/retry.py — ✅ A
- src/henchman/utils/tokens.py — ✅ A

</details>

---

_Report generated by XP Documentation Smell Detector. Smells are static heuristics — use judgement when prioritising fixes._
