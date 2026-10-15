# Context-sized tool discovery

Authorized by the active reliable coding-loop/provider-portability goal. Preserve
explicit context capacity, output reservations, history and authorization.

Evidence: full builtin leader input13722tokens (prompt4465,58tools), configured
capacity8000+default2000output. Restricting to existing leader preset still7858
input, so simple role filtering does not solve request fit. Engineer input8006
with25tools; basic coding tools alone fit. Changing model limits or dropping user
instructions would obscure the actual constraint.

Selected design: try the complete scoped catalog first. On genuine request-size
failure and only when bound builtin discovery exists, prepare a smaller request
with tool_search and up to5 tools explicitly discovered most recently, then add
core coding declarations in priority order when the same whole-request check
allows. Preserve declaration objects and exact output options. Full history,
current turn and all system instructions remain mandatory. Explicit named or
allowed provider tool choices must retain their referenced schemas; unsupported
structured choices reject fallback locally rather than emitting mismatched SDK
payloads. If minimal discovery
or an explicitly requested schema cannot fit, keep the local actionable error.

Reuse ToolSearchTool query/classification logic. Successful discovery records
bounded priority names on its bound registry and reports those names in its
result. Exact names rank first. Builtin searches provide the complete inventory through bounded pages (default5,
limit1..100 and offset>=0); prioritization for schemas uses only executable names
on the shown page. This refinement follows a measured8860-character broad result
that overflowed the next8Krequest at7241input+2000output. No metadata-only capability
is executable. Scope copies get independent ToolSearchTool binding and priority
state, so parent/child discovery does not expose another agent's allowlist.
Default specialist presets include discovery; explicit custom tool lists retain
control. Existing authorization and confirmation still govern all calls.

No new provider-specific SDK path. Original unguarded/None agents retain legacy
behavior. Root owns core selector/Agent integration/tests/docs and packaging;
worker owns registry+ToolSearchTool+focused tests; worker owns preset/scoped-copy
integration+tests. All are shared-worktree edits; no commits or external actions.

Verification: red-first request-fit, next-call discovery, dynamic registrations,
parent/child isolation, failed search and authorization tests; real default
leader8K smoke with actual builtin registry/provider accounting; configured output
caps/current-turn overflow regressions; source+installed-wheel coding workflows.
This work does not qualify a local model or establish whole-task correctness.
