# Missing Contract Tests — Boundary Audit [COMPLETED]

This directory identifies component boundaries in the Henchman-AI codebase
that lacked contract tests. Each `*.md` file covers one subsystem or boundary
category, documents its severity, and describes what a contract test should
validate.

## Status: ALL 17 GAPS FILLED

All identified contract test gaps have been implemented.
380 contract tests now pass in the `tests/contracts/` directory.

## New schema files

- `tests/contracts/schemas/ops/analytics_event.json`
- `tests/contracts/schemas/ops/telemetry_event.json`
- `tests/contracts/schemas/ops/cost_summary.json`
- `tests/contracts/schemas/ops/diagnostic_event.json`
- `tests/contracts/schemas/ops/flag_state.json`
- `tests/contracts/schemas/ops/app_state.json`
- `tests/contracts/schemas/cli/command_result.json`
- `tests/contracts/schemas/cli/pull_request_comment.json`
- `tests/contracts/schemas/api/error_response.json`
- `tests/contracts/schemas/extensions/plugin_database_record.json`
- `tests/contracts/schemas/config/mcp_server_config.json`

## New test files

| File | Gap(s) |
|------|--------|
| `test_security_contracts.py` | #07 Tool security boundary |
| `test_provider_registry_contracts.py` | #12 Provider registry |
| `test_agent_pool_contracts.py` | #14 AgentPool & scoped registry |
| `test_serialization_contract.py` | #16 SerializableDataclass |
| `test_catalog_contracts.py` | #09 Agent catalog & platform manager |
| `test_config_context_contracts.py` | #05 Config context loader |
| `test_protocol_contracts.py` | #17 Cross-subsystem protocols |

## Enhanced existing test files

| File | Gap(s) Added |
|------|--------------|
| `test_ops_contracts.py` | #03 Observability, #04 Flags/State, #13 RateLimiter/Migrations |
| `test_cli_boundary_contracts.py` | #06 Git clients payloads |
| `test_extension_contracts.py` | #08 Extension manager protocol |
| `test_mcp_contracts.py` | #15 MCP manager & auth |
| `test_api_contracts.py` | #11 Error response, chat history, clear history |
| `test_protocol_contracts.py` | #17 AgentInterface, CLI protocol shapes |
