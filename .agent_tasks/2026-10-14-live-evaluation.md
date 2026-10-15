# Live evaluation and installed runtime checkpoint

The preceding goal turn made verified progress (Python-tool contracts and301
focused tests). This turn used the newly unrestricted environment to remove an
actual verification blocker and run live local inference. The whole goal remains
active; no industry-leading or complete-platform claim is established.

## Implemented

- Existing evals/helpers.py now uses the shared provider factory and headless loop.
  Explicit provider choices cannot fall back, whole-turn timeouts are effective,
  exhausted/error terminals fail, and evidence resets per run. Optional AgentConfig
  is copied. Removed the now-unused private duplicate tool-execution path.
- New evals/test_python_reuse.py uses actual tools and independent pytest evidence.
  It requires inspection before editing, unchanged helper/tests, and real reuse
  through a behavioral spy. Oracle checks rejected both the original stub and a
  copied implementation, while accepting genuine helper reuse. Live model passes
  are a separate requirement; no candidate passed this scenario in these probes.
- Live traces exposed AskUserTool's fake successful input. It now requires a real
  nonblank answer from an injected async callback; unbound/invalid/unanswered/error
  and timeout cases fail, cancellation propagates. Default CLI/TUI remain unbound.
  Shared discovery truth and durable docs report that limitation. UI binding is
  explicitly left open in the roadmap, not claimed complete.
- The installed workflow fixture now suppresses child bytecode writes. A same-size
  edit within one timestamp second had let Python reuse stale subtraction despite
  correct file bytes. Deterministic reproduction established the cause before fix.

## Verification evidence

- All12 coding workflow cases passed in the unrestricted development environment.
- Final combined eval-harness + coding-loop gate:28passed in11.49s.
- Shared discovery/help/doctor/tool-manager/documentation gate:28passed in2.93s.
- Ask-user unit contracts:29passed. Combined with eval contracts and REPL flow:
  46passed,1failed. The changed unbound-input REPL flow passed; the unrelated
  greeting/multi-turn test failed as described below. Do not call this suite green.
- Ruff clean across changed code/tests; mypy clean across four source modules;
  scoped diff check clean. Separate bounded review found no material eval-harness
  defects; later input-handler review is recorded in conversation.
- Rebuilt wheel and explicitly force-reinstalled it into a fresh Python3.12.7
  environment after the final production changes. Installed smoke82passed in
  24.71s, with import origin, both CLI aliases, local RAG, real native Linux tools,
  and scripted five-provider edit/test workflows outside the source checkout.
  Logs: portable-wheel-reinstall.log and portable-wheel-linux-final.log.
- Live model results, artifact hashes, argv, failures, and memory exclusions are
  in the local-default-model checkpoint. Two small candidates failed both tasks;
  a separate rerun after input repair also failed. All owned servers stopped.

Counts overlap and must not be added into a single total. No full-suite pass,
native Windows/macOS result, live remote-provider result, or physical8GB-laptop
measurement is claimed. No project commit, push, staging, or publication occurred.

## Next work with concrete evidence

- tests/ui_integration/test_repl_e2e.py::TestReplE2E::test_multi_turn_conversation
  expects two messages after greeting Hi but receives three, including an
  orchestrator reasoning-format complaint. The no-action error comes from
  agents/orchestrator_run.py; injected review text from orchestrator_validation.py.
  No ask_user call occurs in this failing path. Investigate intended conversational
  vs implementation behavior; do not weaken the assertion to hide extra messages.
- Bind real REPL/TUI question channels and verify answer/timeout/cancellation. The
  current repair establishes truthful failure and an embeddable callback only.
- Evaluate a newer small model or modestly larger candidate against the same task
  requirements. Add whole-application memory/context accounting and managed model
  acquisition/startup/shutdown before claiming an included local default.
- SDK client ownership/async closure in EvalTestRig cleanup remains preexisting
  work. The scratch live probe explicitly closes its owned compatible client.
- Native OS jobs, stronger Python/reuse/smell analysis, environment-aware DevOps,
  and evaluated team leadership remain in the full active roadmap.
