# Local model research: 16 GB RAM with optional GPU acceleration

Research date: 2026-10-14. The user's revised target is **16 GB RAM**, retaining
CPU operation and adding optional GPU support. This supersedes the earlier 8 GB
target for future evaluation; it does not retroactively change earlier results.
This research task downloaded no weights, started no model servers, and modified
no runtime settings. Only this artifact was written.

## Decision and retained failures

**Next live probe: Qwen3-4B-Instruct-2507 Q8_0 from ggml-org.** This tests an updated,
non-thinking-only instruction model with an independently verifiable runtime-team
conversion. It is an engineering candidate, not a selected included default.
**Backup: Qwen3.5-4B Q8_0 from Unsloth**, explicitly a third-party quantization of
Qwen's official model. The backup changes architecture and tool format as well as
training generation, so keep its results separate.

Prior evidence remains in [the earlier local-model report](2026-10-14-local-default-model.md)
and `local-model-probe/`:

| Tested configuration | Actual task result |
|---|---|
| Qwen2.5-Coder-1.5B-Instruct Q4_K_M | 0/2; emitted prose/fenced JSON without structured calls, left targets unchanged. |
| Qwen3-0.6B Q8_0 | 0/2; genuine calls but incorrect edits/reuse failures. |
| Qwen3-0.6B Q8_0 after truthful user-input fix | 0/2; independent collection failure or unchanged implementation. |
| Qwen3-1.7B Q8_0 | 0/2; promised arithmetic repair without editing, and stalled on reuse. |

Sources are the saved `results.json`, `qwen3-results.json`,
`qwen3-after-input-fix.json`, and `qwen3-17b-results.json`. Their Linux desktop
measurements excluded OS/editor/RAG/test children and did not establish laptop
acceptance. None qualifies as an included default. Keep the existing behavioral
oracles, unchanged-test guards, and failed trajectories when comparing candidates.

## Next candidate and exact artifact

The [official model card](https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507)
describes an updated 4B instruction model with improved coding/tool use, native
262,144-token context, and non-thinking-only output. It recommends temperature
0.7, top_p 0.8, top_k 20, min_p 0; presence penalty can be adjusted from 0 to 2.
Those publisher claims motivate a probe; they do not prove Henchman task success.

The [GGUF card](https://huggingface.co/ggml-org/Qwen3-4B-Instruct-2507-Q8_0-GGUF)
identifies this as ggml-org's conversion of Qwen's base. **It is published by the
runtime team, not by Qwen.** The queried Qwen-owned
`Qwen3-4B-Instruct-2507-GGUF` endpoint returned HTTP 401 unauthenticated; that only
establishes that this endpoint was not accessible during this research.

Pinned metadata, obtained from the [publisher API](https://huggingface.co/api/models/ggml-org/Qwen3-4B-Instruct-2507-Q8_0-GGUF?blobs=true):

```json
{
  "repository": "ggml-org/Qwen3-4B-Instruct-2507-Q8_0-GGUF",
  "revision": "e6f794d44f9395d0184a966c27b5ae99ea356fcb",
  "filename": "qwen3-4b-instruct-2507-q8_0.gguf",
  "bytes": 4280403520,
  "sha256": "ae916ede1c010a26955ee8ae2e908bf8815a3f135ec860439ab924701c69d5f1",
  "url": "https://huggingface.co/ggml-org/Qwen3-4B-Instruct-2507-Q8_0-GGUF/resolve/e6f794d44f9395d0184a966c27b5ae99ea356fcb/qwen3-4b-instruct-2507-q8_0.gguf"
}
```

Official base revision observed: `cdbee75f17c01a7cc42f958dc650907174af0554`.
The current base revision is not asserted to be the exact conversion input commit;
the GGUF card names the base repository but does not pin that input revision.

Redistribution: the [base LICENSE](https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507/blob/cdbee75f17c01a7cc42f958dc650907174af0554/LICENSE)
is Apache-2.0; the GGUF metadata identifies the same license. Redistribution under
that license requires retaining its license/notices and identifying modifications
as applicable. Preserve both model and converter provenance in any bundled profile.
The GGUF repository lists no separate LICENSE artifact, so a future distribution
must include the applicable upstream license rather than relying on its metadata
label alone.

## Backup and exact artifact

[Qwen3.5-4B's official card](https://huggingface.co/Qwen/Qwen3.5-4B)
documents tool use with the qwen3_coder parser and supports non-thinking via
`chat_template_kwargs: {"enable_thinking": false}`. For that mode's general-task
profile, it recommends temperature 0.7, top_p 0.8, top_k 20, min_p 0,
presence_penalty 1.5, repetition_penalty 1.0. It thinks by default; do not rely on
Qwen3's `/no_think` prompt switch. Its separate reasoning-task recommendations
are inconsistent between two sections of the current card; avoid silently mixing
those profiles.

[Unsloth's GGUF repository](https://huggingface.co/unsloth/Qwen3.5-4B-GGUF)
is the quantization publisher used for this backup. Public Qwen-owned
`Qwen3.5-4B-GGUF` and ggml-org-owned `Qwen3.5-4B-GGUF` endpoints returned HTTP 401
in these unauthenticated checks; no assertion of their nonexistence is made.

Pinned metadata from the [quantization publisher API](https://huggingface.co/api/models/unsloth/Qwen3.5-4B-GGUF?blobs=true):

```json
{
  "repository": "unsloth/Qwen3.5-4B-GGUF",
  "revision": "e87f176479d0855a907a41277aca2f8ee7a09523",
  "filename": "Qwen3.5-4B-Q8_0.gguf",
  "bytes": 4482403488,
  "sha256": "10cc391b403021dd11c614679d2fd92f611c3681d29e29651b717316965d61e1",
  "url": "https://huggingface.co/unsloth/Qwen3.5-4B-GGUF/resolve/e87f176479d0855a907a41277aca2f8ee7a09523/Qwen3.5-4B-Q8_0.gguf"
}
```

Official base revision observed: `851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a`.
Again, this is a current base snapshot, not a verified conversion-input pin.
Both the quantization metadata and the [official base LICENSE](https://huggingface.co/Qwen/Qwen3.5-4B/blob/851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a/LICENSE)
identify Apache-2.0. Preserve the upstream license and quantizer attribution.
Use text only in the first probe; no vision projector or image pipeline is needed.

## Compatibility with the existing pinned runtime

The local command `runtime/llama-b11617/llama-server --version`, run without a
model, returned build 11617, commit `14310190c`, GNU 11.4.0, Linux x86_64.
The [official release](https://github.com/ggml-org/llama.cpp/releases/tag/b11617)
resolves to commit `14310190cd0a0c831fe949ac8cbedd8abdc90695` and is marked prerelease.
Existing CPU archive metadata remains in `local-model-probe/artifacts.json`.

Evidence for compatibility, rather than a claim of a completed new-model run:

- The pinned [architecture registry](https://github.com/ggml-org/llama.cpp/blob/b11617/src/llama-arch.cpp)
  includes both `qwen3` and `qwen35`.
- Qwen3-4B-Instruct-2507's official [tokenizer configuration](https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507/blob/cdbee75f17c01a7cc42f958dc650907174af0554/tokenizer_config.json)
  carries a Jinja tools block and serializes tool requests/results. Keep the GGUF's
  embedded template; do not replace it with a plain ChatML template that might omit
  the tools. Verify the embedded template and observed parser after loading.
- Pinned [chat.cpp](https://github.com/ggml-org/llama.cpp/blob/b11617/common/chat.cpp)
  explicitly routes Qwen3.5's XML function/parameter tags to the Qwen3-Coder parser.
- Pinned [server documentation](https://github.com/ggml-org/llama.cpp/blob/b11617/tools/server/README.md)
  provides `/v1/chat/completions`, `chat_template_kwargs`, and model-dependent
  parallel tool calls. Reuse Henchman's compatible provider and native structured
  tool events; never execute text merely because it resembles a call.
- The [function-calling guide](https://github.com/ggml-org/llama.cpp/blob/b11617/docs/function-calling.md)
  documents Jinja-based tool handling. Prior live Qwen3 probes also established
  structured tool transport on this pinned runtime, but not this new GGUF's exact
  template or its coding reliability.

The runtime is [MIT licensed](https://github.com/ggml-org/llama.cpp/blob/b11617/LICENSE).
Preserve its license alongside model notices and any backend-library licenses.

## Proposed initial CPU profile and evaluation

These are explicit experiment settings, not hardware-fit guarantees:

- One model process, one server slot (`--parallel 1`), four CPU threads initially,
  `--n-gpu-layers 0`, `--device none`, `--ctx-size 4096`, and `--jinja`.
- Preserve the original rig's 3072-token input budget and 512-token response cap
  for the first comparison, seed 42, and unchanged behavior oracles. Record any
  length truncation as a failed/incomplete attempt; a separately named larger
  context/output experiment may follow. The model card's much larger output
  recommendation is not this bounded experiment's profile.
- Next model sampling: temperature 0.7, top_p 0.8, top_k 20, min_p 0,
  presence_penalty 0 initially. The last value is our explicit neutral choice,
  not a fixed publisher recommendation. It differs from earlier Qwen3 probes'
  presence penalty of 1.5 and must be reported with results.
- First inspect streaming tool-call identity, arguments, actual tool execution,
  and a follow-up turn. Then run arithmetic repair and existing-helper reuse,
  followed by test-failure recovery, bounded cancellation, and broader Python
  tasks if the initial pair passes. Keep every failure/diff and immutable test
  fixture; model prose and terminal status are not acceptance oracles.
- An 8K-context trial must account for schema/prompt overhead, KV cache, buffers,
  embeddings/RAG, agent process, test children, editor and OS. Larger context is
  a new measured profile, not an automatic consequence of the model's advertised
  maximum. Do not spawn one model process per specialist.
- The 4.28 GB and 4.48 GB file sizes make these reasonable 16 GB candidates to
  investigate. They are not working-set bounds. Measure whole-workflow peak
  memory and useful task latency on physical 16 GB hardware before accepting a
  default; a large desktop, cgroup, or GPU run is different evidence.

## Optional GPU runtime artifacts and prerequisites

CPU remains a usable baseline. CUDA for NVIDIA, Metal for supported Macs, and
Vulkan for compatible devices are supported backend paths in the pinned
[build guide](https://github.com/ggml-org/llama.cpp/blob/b11617/docs/build.md).
Select based on actual device/driver availability, not a presumed user GPU.
The CPU artifact already present does not contain the CUDA/Metal/Vulkan backends.

The root agent separately found an RTX 3090 with 24 GB VRAM and driver
580.178.04, plus Intel HD530, on this host. This research confirmed Ubuntu 26.04.1,
glibc 2.43, a Vulkan loader and `libcuda.so.1`; `ldconfig` exposed only CUDA 9.0
cudart/cuBLAS libraries. This host can support an optional GPU experiment, but
its hardware does not certify a typical 16 GB laptop.

Exact assets from the [official release API](https://api.github.com/repos/ggml-org/llama.cpp/releases/tags/b11617):

| Artifact | Bytes | SHA-256 |
|---|---:|---|
| `llama-b11617-bin-ubuntu-cuda-12.8-x64.tar.gz` | 171623026 | `1c5024dfa587a3f23ef8fc066cb2578fb43d661910d4111a8941184773c237d1` |
| `cudart-llama-b11617-bin-ubuntu-cuda-12.8-x64.tar.gz` | 594377703 | `59e7bf466cf7d307c2ef9654fc4a5ba5428a4dd1e63b60fbe1b8d8591550f54f` |
| `llama-b11617-bin-ubuntu-vulkan-x64.tar.gz` | 30399620 | `9a41faa40d58bcabf6447df29df122bd63346baa5ca078a8f371f6c9b14232ce` |

Pinned-tag download URLs (verify the SHA-256 values above):

- [CUDA 12.8 runtime binary](https://github.com/ggml-org/llama.cpp/releases/download/b11617/llama-b11617-bin-ubuntu-cuda-12.8-x64.tar.gz)
- [Matching CUDA libraries](https://github.com/ggml-org/llama.cpp/releases/download/b11617/cudart-llama-b11617-bin-ubuntu-cuda-12.8-x64.tar.gz)
- [Vulkan runtime binary](https://github.com/ggml-org/llama.cpp/releases/download/b11617/llama-b11617-bin-ubuntu-vulkan-x64.tar.gz)

Prefer CUDA 12.8 for the first optional RTX 3090 experiment. The pinned
[release workflow](https://github.com/ggml-org/llama.cpp/blob/b11617/.github/workflows/release.yml)
builds that artifact in a CUDA 12.8.2 Ubuntu 24.04 container. Its separate library
archive contains `libcudart.so.12`, `libcublas.so.12`, and `libcublasLt.so.12`.
Place these in an isolated owned runtime directory and expose them only to that
process's loader; do not replace the user's CUDA installation. Check actual ELF
loader dependencies after extraction and confirm `--list-devices` before loading
weights. No compile or system-wide driver/toolkit install is needed merely to
try these supplied binaries, assuming their runtime dependencies resolve.

NVIDIA's [compatibility documentation](https://docs.nvidia.com/deploy/cuda-compatibility/minor-version-compatibility.html)
allows CUDA 12 applications on newer drivers through backward compatibility.
Thus driver 580 is a plausible starting point, not an execution result. The
actual CUDA backend, device detection, model load and tool-loop behavior still
need tests. Vulkan additionally needs a working compatible device driver/ICD;
a loader library alone proves neither device support nor speed.

For GPU comparison retain model hash, context, prompt/output budget, seeds and
behavior oracles. Record selected device, offloaded layers, VRAM and host memory,
latency, and all task results. Start with a bounded explicit offload profile;
llama-server help confirms device selection and exact/auto/all GPU layer controls.
If acceleration is unavailable, report it and use the CPU profile; never silently
switch to a paid remote endpoint. Native Windows/macOS backend execution,
portable installer/lifecycle, and integrated 16 GB acceptance remain open.
