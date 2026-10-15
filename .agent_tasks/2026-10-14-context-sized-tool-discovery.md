# Context-sized tool discovery

Previous goal turn: progress (request budgeting and exact model-switch repair
verified). This turn also changes authoritative production state and adds real
provider/tool-loop evidence. The full user goal remains active and unproven.

## Problem and behavior

The previous request guard exposed that the default leader's full builtin
catalog could not fit its 8000-token capacity. Existing leader preset filtering
still measured7858 input before output; changing that scope alone would not fix
request fit. The engineer also had8006 input with 25 schemas before discovery.

The Agent now tries its complete registered catalog, then uses bounded discovery
only when required input+tools+output cannot fit and the registry has a bound
builtin search tool. Required schemas include search, names from the latest
search page (up to 5), and supported provider-forced/allowed named functions.
Unknown structured choices reject reduction. Optional core tools are added in
priority order only when the same whole-request estimator permits them.

No execution scope, confirmation policy, message body or original history is
changed. Explicit custom scopes without discovery retain local overflow. Large
required prompt/results/output/requested schemas still fail locally. New user
turns reset discovery priorities. Legacy None-capacity agents retain full-catalog
behavior.

Builtin search copies bind independently to each specialist registry; parent
searches and allowlists remain separate. Default presets include search; explicit
custom lists stay explicit. Registry support tracks the actual bound tool
identity, preventing an unrelated same-name replacement from enabling discovery.
Engineer eval logging preserves that identity contract on its known wrapper.

## Pagination and discovered defects

A broad search initially returned8860 characters and made the next 8K request fail
at estimated7241 input + 2000 output. Search results now default to 5 entries; limit is
an integer 1..100 and offset a nonnegative integer, with bools rejected. Pages
cover executable rows then shared capability-classification rows. Results report
total/nextoffset, and only shown executable names receive priority. Complete
inventory remains reachable through pagination and /tools.

Review reproduced a forced pytest_run choice with its schema omitted by fallback.
Required provider names now preserve top-level and extra_body precedence and
supported SDK allowed_tools shapes. Unavailable names cannot expand agent scope;
required schemas that cannot fit reject before transport.

The five-provider workflow found Ollama rejected saved output caps. It now forwards
compatible request defaults. Its early unsupported-option rejection is retained
using the installed SDK create signature before a runtime switch mutates refs;
this fixed the installed-wheel regression in invalid provider selection.

## Verification

- Root red: 8 disclosure contracts, then 2 forced-choice cases; broad continuation
  red confirmed 7241 + 2000 overflow. Eval wrapper discovery also observed red.
- Worker red: 9 discovery contracts + same-name replacement; 4 scoping contracts;
 26 required-schema contracts;14 pagination failures before implementation.
- Final source integration:313 passed in 32.32s, tool-disclosure-source.log.
- Ruff 18 changed files clean; mypy 11 source/helper files clean. Legacy Tier1 test
  helper has 2 unrelated annotation errors; no whole-tree mypy claim.
- Independent review closed forced-choice finding with 48 focused tests and no
  further blocking findings in that reviewed scope.
- Five real adapters (OpenRouter, compatible, DeepSeek, Ollama, native Anthropic)
  use scripted SDK transport at 8K. Actual builtin discovery/read/pytest/edit/
  pytest recovery runs; tests verify schema present for every tool call, input
  plus explicit 1024 output within capacity, failure then passing test output,
  retained approvals, file result and runtime completion. No inference claim.
- Full Textual clarification/session flow restored to default 8K and passes;
  prior temporary 32K fixture override removed.
- Final installed-wheel suite: 770 passed in 66.37s, outside the checkout. CLI
  aliases and local RAG smoke checks also passed. Full log:
  tool-disclosure-final-wheel-linux.log.

The wheel is forceinstalled into portable-wheel-env and checked outside checkout
(Python3.12; source tests Python3.14). Artifact:
tool-disclosure-final-wheel/henchman_ai-0.3.17-py3-none-any.whl.
The earlier tool-disclosure-wheel is retained as a failing intermediate artifact
(1 invalid-config test failed / 754 passed), not the final deliverable.

## Estimated accounting snapshot

See tool-disclosure-8k-accounting.json, zero model calls:

- Full initial catalog:13850 estimated input, 58 tools.
- Reduced initial request:5977 input + 2000 reserved output<=8000.
- After broad paginated search:5949 input + 2000 output<=8000.
- Broad search result:1082 characters (earlier 8860).

Counts depend on provider formatting/tokenizer/template; they are estimates and
not a server guarantee, memory bound, benchmark or physical 16GB laptop test.

## Remaining goal work

Live task correctness/team effectiveness, adequate verification and Python reuse,
DevOps/release evidence, longer-turn context/memory management, leader custom
scope consistency including late allowed MCP registrations, native Windows/macOS
CI results and physical 16GB hardware validation remain open. Prior local model
quality 2/4 is not upgraded by these offline tests. No new model probes or cloud
calls, staging, commit, push or deployment occurred in this turn.
