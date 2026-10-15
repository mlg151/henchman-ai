Goal: start enforcing executable contracts across active Henchman runtime boundaries.

Status: initial tranche implemented

Scope for this tranche:
- add a real `tests/contracts/` harness
- define JSON-Schema-style contracts for high-value API and runtime payloads
- add consumer/provider contract tests for API, core runtime, and MCP seams
- tighten the shared contract validator so the schemas are executable

Notes:
- this tranche targets active runtime code under `src/henchman/`
- contract format is mixed by seam, but the first implementation uses JSON-Schema-style
  payload contracts where that gives the most leverage
- follow RED -> GREEN -> REFACTOR; tests land before supporting code
- landed artifacts:
  - `tests/contracts/` harness, helpers, and schema fixtures
  - API contract tests for health, chat, and remote/OAuth seams
  - runtime contract tests for provider/tool/event/MCP payloads
  - protocol contract tests for chat/delegation/doctor plus git/PR/Textual/orchestrator seams
  - expanded `henchman.testing.ContractSuite` JSON-schema subset validation
- remaining follow-up:
  - extend coverage to remaining active runtime seams not yet modeled as contracts
  - add stronger drift checks for public docs and any exported machine-readable API schema
  - run focused pytest/ruff/mypy slices when command execution is available
