# Live team tool scopes

Goal: reliable Python team leadership with explicit role boundaries. Prior turn
was progress: context-sized tool discovery verified with 313 source and 770
installed-wheel tests. This plan fixes a current runtime mismatch rather than
claiming the full goal is complete.

Evidence: setup_tech_lead receives merged configs but passes the entire root
registry, ignoring the leader tools/auto_approve lists. create_scoped_registry
copies only tools already present; initialize_mcp registers asynchronously later.
A static scoped copy would remove late explicitly allowed MCP tools and preserve
removed/replaced tool instances. Search must stay scope-bound after replacements.

Design: a ScopedToolRegistry subclass holds a parent reference, immutable allowed
names, local overrides and explicit local exclusions. All observable lookup,
inventory, declaration and authorization paths resolve the same live view.
Allowed late registrations appear; unallowed names do not. Parent removals and
replacements flow through absent local overrides. Explicit local register/unregister
keeps its existing ability to override/add/remove scope entries. Extra tools win.
Builtin tool_search is cloned lazily per source identity and scope; replacement
invalidates stale copies and metadata. Discovery priorities remain per registry.

Base registry methods use virtual get/list lookup where needed. Plan mode and
confirmation continue to resolve live parents. Existing specialist local
approval behavior stays explicit. The new leader scope follows root automatic
approval decisions as well as its configured local approvals to preserve the
former root acting-registry behavior; an internal optional inherit_auto_approve
flag defaults false for other scopes. Plan mode is checked before approvals.

Leader setup uses the merged leader.tools/auto_approve without unioning the full
catalog or automatically adding delegate_task to the scope. A builtin delegate
can remain registered in the parent for role allowlists. Default leader preset
adds verify_plan_execution (EXECUTE approval) for existing acceptance workflow;
custom lists gain nothing implicitly. Default includes shell/git/knowledge-write
operations, so documentation must not describe this as enforced read-only access.

Before claiming the boundary, inspect normal UI/headless/API execution to ensure
all paths authorize against the acting agent scope. A root registry remains the
full runtime inventory used for registration/discovery/settings, not a substitute
for actor authorization. Add regressions for any actual bypasses found.

Ownership: worker owns tools/registry.py, new tools/scoped_registry.py,
agents/pool.py factory, new tests/tools/test_live_tool_scopes.py. Root owns leader
setup/preset integration, regression workflows/docs/packaging. A read-only agent
traces execution paths and later reviews. Shared worktree: preserve other edits.

TDD: default/custom leader, explicit approvals, allowed late registration,
unallowed late registration, removals/replacements, extras precedence, nested
scopes, scope-bound search replacement, current parent policies and real delegated
read/edit/test/review flow. Keep original acceptance assertions; tests requiring
custom tools should declare those tools, not expand default roles to pass tests.
Run focused source/Ruff/mypy, then fresh installed-wheel workflows. No external
model calls, staging, commits, push or deployment needed for this slice.
