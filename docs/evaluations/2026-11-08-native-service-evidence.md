# Native service evidence — 2026-11-08

At commit `296b5564058475da2420de005ee6572fe4586987`, all twelve
installed-wheel jobs completed on Python 3.11–3.14 across Linux, macOS and
Windows. Every job failed the same goal-disclosure fixture; **the overall CI
run did not pass**. The [receipt](2026-11-08-native-service-evidence.json) links
each job and records its denominator and sole failure.

| Platform | Passed per job | Failed per job | Skipped per job |
|----------|----------------|----------------|-----------------|
| Linux, each of four Python versions | 5,467 | 1 | 25 |
| macOS, each of four Python versions | 5,465 | 1 | 27 |
| Windows, each of four Python versions | 5,370 | 1 | 122 |

The fixture assumed `goal_status` was always disclosed initially. The enlarged
catalog correctly required exact-name tool discovery at its context limit.
Commit `d8bf94d42d75f439bdc1ea50ec7bd77c52ab06f8` repairs that assumption and
covers both discovered and initially available schemas within the actual
request budget. Its local checks pass; that does not retroactively change these
CI results.

The completed cohorts provide evidence for the installed checkpoint service:
its staged tests include exact-byte edit/create/delete/rename restoration,
individual text hunks, preservation of unrelated dirty content and the Git index,
interleaved user conflicts, private retention, denied/secret/unsupported content,
legacy non-restorable records, verification invalidation and interrupted restore.
The Windows tests use actual Win32 handles, NTFS and process termination at eight
restore boundaries; equivalent POSIX recovery tests use actual subprocesses.
The shared CLI and rendered Textual adapters are also staged. These modules had
no failures in the completed cohorts. Skipped cases, including any unavailable
symlink privilege, remain unqualified.

See [checkpoint behavior and platform limits](../checkpoints.md),
[the native tests](../../tests/advanced/test_checkpoint_windows.py),
[shared service tests](../../tests/advanced/test_checkpoints.py) and
[the artifact staging list](../../tests/testing/installed_wheel_smoke.py).
This evidence does not establish native terminal usability, screen-reader
behavior, arbitrary filesystem support, a clean aggregate suite, or final
v0.4.2 artifact qualification. Those remain separate release requirements.

The same staged cohorts also include canonical schema/registry contracts, all five
provider projection profiles, independent MCP catalog/refresh fixture servers,
actual SDK stdio protocol negotiation, and typed tool-result retention. Those
modules had no failures in these completed cohorts. The
[supported compatibility scope](../standards.md#implemented-compatibility-foundation-v042-work)
remains bounded to its explicit schemas, SDK and protocol profiles; hosted model
quality, real OAuth accounts and general external conformance are separate.
