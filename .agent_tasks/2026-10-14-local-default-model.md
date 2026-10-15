# Included local default: 8 GB CPU laptop

User requirement: a tiny, useful included local default model, with an 8 GB RAM
laptop as the baseline. CPU-only is the stated assumption. No included default
has been selected. The unrestricted follow-up below records actual downloads and
live probes; the initial research section preceded those experiments.

## Live CPU probe: first candidate

- Downloaded official Qwen2.5-Coder-1.5B-Instruct Q4_K_M from revision
  f86cb2c1fa58255f8052cc32aeede1b7482d4361 and llama.cpp CPU release b11617
  (commit 14310190c). Verified both against published SHA-256/size metadata.
  Exact artifact URLs/hashes are in `local-model-probe/artifacts.json`.
- Runtime: Linux x86_64, i7-6700K, 60 GiB host RAM, four CPU threads, one slot,
  4096 context, zero GPU layers. Agent input budget3072, output cap512, seed42,
  temperature0. Eval rig has no RAG. Other validation work overlapped this probe;
  this is exploratory functional evidence, not an isolated latency benchmark.
- Both actual live tasks failed (0/2): arithmetic repair and reuse of an existing
  normalizer. The model returned fenced JSON text but no structured tool calls;
  neither task edited its target. Normal stream termination is correctly distinct
  from behavioral success. No attempt was made to execute prose as a tool call.
- Durations50.27s/12.69s. Sampled combined server+agent RSS peaked2,201,636KiB
  (about2.10GiB), excluding test children, editor, OS, and RAG; shared pages can be
  counted twice. This is not an 8 GB laptop acceptance measurement.
- Evidence: `local-model-probe/results.json`, `probe.log`, `server.log`, and
  `run_probe.py`. The temporary owned server was stopped after the run; the user's
  preexisting Ollama service and model inventory were not changed.
- Decision: this candidate/configuration does not qualify as the included default.
  Test a model with a different tool-use/template path before choosing weights.

## Live CPU probe: second candidate

- Downloaded [official Qwen3-0.6B Q8_0](https://huggingface.co/Qwen/Qwen3-0.6B-GGUF)
  from revision23749fefcc72300e3a2ad315e1317431b06b590a (639,446,688bytes),
  checked its published SHA-256, and reused the pinned CPU runtime. Same context,
  threads, slot and output budgets; non-thinking mode with temperature0.7, top_p0.8,
  top_k20, min_p0, presence_penalty1.5, seed42 per the card's sampling guidance.
- Both tasks failed (0/2), despite genuine structured tool calls. Arithmetic
  repair renamed add to addition but retained subtraction; independent pytest
  failed import. Reuse produced `return values`, skipped helper inspection and
  verification, and asked repeatedly for input. Preserve these failures as
  evidence; native tool-call support alone does not qualify a coding agent.
- Durations133.21s/68.73s; sampled server+agent RSS peak1,459,872KiB (about1.39GiB),
  with the same exclusions as the first probe. No physical8GB/laptop acceptance
  result is claimed. Runtime stopped normally at the end.
- Evidence: local-model-probe/qwen3-results.json, qwen3-probe.log and
  qwen3-results-server.log. Exact argv/request settings saved with results.
- A separate existing bug appeared in trajectories: unbound AskUserTool reports
  placeholder text as successful input. Fix its result contract before subsequent
  probes. Both models already made incorrect/missing edits independently of this
  bug; reruns after repair must be recorded separately, never overwrite failures.

## Rerun after truthful user-input handling

Qwen3-0.6B Q8_0 was rerun with the corrected AskUserTool declaration/result contract
and otherwise the same runtime, prompt tasks, and sampling settings. Both cases
still failed (0/2): arithmetic source raised NameError during independent test
collection; reuse only listed files and left the implementation unchanged.
Durations74.19s/18.29s, sampled server+agent RSS peak1,428,176KiB (about1.36GiB).
Evidence is separate: local-model-probe/qwen3-after-input-fix.json and its logs.
All owned model server processes were stopped. Neither a small memory footprint
nor normal completion is treated as successful task execution.

Neither candidate/configuration qualifies as the included default. Next compare a
newer small tool-capable model and/or a modestly larger quantization within the
8GB whole-application budget. Do not relax the Python behavior/reuse checks to fit
the smallest file. Managed installer/runtime lifecycle and UI input binding remain
implementation work, not fulfilled by this scratch evaluation supervisor.

## Initial primary-source candidates (2026-10-14)

These are evaluation candidates, not performance recommendations. Weight-file
size is not total resident memory; published benchmarks do not establish Henchman
tool-loop reliability or useful latency on the target laptop.

| Candidate | Evidence | Decision still needed |
| --- | --- | --- |
| Qwen2.5-Coder-1.5B-Instruct GGUF | Official card lists Apache-2.0, 1.54B parameters, and Q4_K_M weights around 1.12 GB. | Compare Python usefulness and structured tool calls against newer small models. |
| Qwen3.5-0.8B | Official card lists Apache-2.0 and defaults to non-thinking mode; warns that thinking can loop. | Verify pinned CPU runtime/quantization compatibility and bounded context; do not inherit the large advertised context. |
| LFM2.5-1.2B-Instruct | Official card documents function calling and official GGUF artifacts. LFM1.0 has a commercial revenue threshold, unlike Apache-2.0. | Assess distribution suitability before treating it as an included default; test runtime conversion of model calls into standard tool events. |

Sources:

- [Qwen2.5-Coder official GGUF card](https://huggingface.co/Qwen/Qwen2.5-Coder-1.5B-Instruct-GGUF)
- [Qwen3.5-0.8B official card](https://huggingface.co/Qwen/Qwen3.5-0.8B)
- [Liquid official model card](https://huggingface.co/LiquidAI/LFM2.5-1.2B-Instruct)
- [Liquid official GGUF card](https://huggingface.co/LiquidAI/LFM2.5-1.2B-Instruct-GGUF)
- [Liquid model license](https://huggingface.co/LiquidAI/LFM2.5-1.2B-Instruct/blob/main/LICENSE)
- [llama.cpp server documentation](https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md)

llama.cpp is a runtime candidate because its local compatible chat endpoint can
reuse Henchman's provider layer. Its documented context, output, thread, and slot
controls should be explicit in a pinned profile. Keep Henchman responsible for
tool execution; server-side built-in tools are a separate facility, not required.

## Proposed evaluation constraints

These are initial engineering targets, not measured guarantees:

- Start with one loaded model and one generation slot, CPU-only; queue specialist
  work instead of multiplying model processes. Test a 4K context first and compare
  8K only when the whole-process memory and task results justify it.
- Measure model server plus Henchman, prompt processing, first-token latency,
  generation rate, peak memory, and behavior with the editor/development tools
  present. Leave OS/application headroom; an 8 GB cgroup limit on a larger machine
  does not reproduce laptop CPU or memory-bandwidth performance.
- Include deterministic Python fixtures: find/reuse an existing implementation,
  make a bounded edit, run tests, repair a failing test, reject malformed calls,
  and cancel stalled generation. Record actual diffs and subprocess evidence.
- Compare model/runtime/quantization revisions on identical tasks and seeds where
  supported. Save failures, not just aggregate scores. Do not infer team-lead
  competence from small isolated code-generation benchmarks.
- Included experience must cover artifact acquisition/integrity, license notices,
  readiness, configuration, resource bounds, shutdown, and offline reuse. Merely
  documenting external Ollama installation does not meet this requirement.
- Preserve OpenRouter as the primary remote integration and independent providers.
  Local failure must not silently initiate paid remote requests.

## Next implementation boundary

First reuse the existing local compatible provider and shared construction path.
Inspect model catalog/config/runtime lifecycle seams before adding abstractions.
Build artifact/profile and owned-process lifecycle contracts separately from model
selection, then test the real model through the existing coding loop. Native OS
runtime artifacts and laptop measurements remain acceptance requirements.

Focused repository exploration confirms the existing transport seam:

- `src/henchman/providers/ollama.py` wraps the compatible provider and normalizes
  its configured origin; `OLLAMA_HOST` and the localhost default already work.
- `src/henchman/providers/factory.py` centralizes construction and validates
  configuration without proving network readiness. Reuse it for managed-local
  configuration rather than introducing another message/tool transport.
- Current Ollama model listing contains static examples, not an installed inventory.
  No managed download, startup, health check, or CPU/context/keepalive controls were
  found in that slice. `docs/providers.md` requires manual install/pull/serve.
- Provider settings still default to DeepSeek. A future included local default needs
  explicit first-run selection/migration semantics that preserve saved user choices.
- Context settings are not a hardware budget: config/schema.py defaults to 8,000
  tokens and 75% compaction, core Agent auto limits use 85% of the model lookup,
  and utils/tokens.py lists llama3.2 at 131,072 (unknown models: 8,000). Align prompt
  budget, tool schema overhead, output reserve, and runtime KV/context explicitly.
- RAG defaults enabled. CLI initialization uses index=False but RagSystem still
  constructs FastEmbedProvider/TextEmbedding. Include this memory consumer in the
  lightweight profile; loading only one small generation model is insufficient.
- Existing test seams: tests/providers/test_ollama.py, test_factory.py,
  tests/contracts/test_ollama_provider_contract.py, and
  tests/integration/test_context_limits.py. Mock stream contracts are not local
  inference or hardware measurements. The one-shot Python subprocess helper is
  not a persistent model-server supervisor.

## Third candidate: Qwen3-1.7B Q8_0

- Official model: https://huggingface.co/Qwen/Qwen3-1.7B-GGUF, revision
  90862c4b9d2787eaed51d12237eafdfe7c5f6077. Download size 1,834,426,016 bytes;
  SHA256 061b54daade076b5d3362dac252678d17da8c68f07560be70818cace6590cb1a,
  verified against publisher API metadata. Exact URL in artifacts.json.
- Same pinned CPU runtime, four threads, 4096 context, 3072 input budget and 512
  response cap, non-thinking Qwen3 sampling parameters and seed42 as the 0.6B probe.
  Arithmetic probe now additionally rejects changes to the verification fixture.
- **0/2 tasks passed.** Arithmetic read source and test correctly, then announced
  an intended fix without editing or testing. Independent pytest failed on -1 vs5.
  Reuse listed files and found the normalizer declaration, then repeatedly searched
  for that helper in the caller and stopped claiming it could not proceed. The
  caller remained NotImplementedError; behavioral assertion rejected it.
- Durations 55.68s / 156.87s. Sampled combined server+agent RSS peak 2,648,744KiB
  (about2.53GiB); server peak2,407,868KiB, agent peak240,876KiB. Excludes children,
  RAG, OS/editor and can double-count shared pages. Host has60GiB, no8GBlimit.
  Installed-artifact checks overlapped this exploratory run; not a latency benchmark.
- Evidence: local-model-probe/qwen3-17b-results.json, qwen3-17b-probe.log,
  qwen3-17b-results-server.log. Runtime exited0 and no owned server remains.
- Decision: do not select this candidate/configuration as included default.
  Runtime stop success is separate from task success. Merely raising the parameter
  count within this family did not establish useful task completion in these runs.
  Next evaluate newer small tool-capable models; retain these failures and task
  oracles, and add varied tasks before any default selection.
- The long arithmetic promise bypassed existing StallDetector's120character
  intent threshold. Do not simply broaden keyword nudges: conversational completion
  and action-task evidence need an explicit contract, already tracked separately.
