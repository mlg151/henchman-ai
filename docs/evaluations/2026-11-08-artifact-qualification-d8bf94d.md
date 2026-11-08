# Development artifact retry — 2026-11-08

The real release qualification command passed both installed artifact profiles
at `d8bf94d42d75f439bdc1ea50ec7bd77c52ab06f8` on Linux/Python 3.12.13.
Each profile passed 5,663 tests and skipped 25, including the available Neovim
0.12.6 editor fixtures. The source archive rebuilt the same wheel hash.

| Artifact | Passed / skipped | Test duration | Result |
| --- | ---: | ---: | --- |
| Wheel in a fresh environment | 5,663 / 25 | 967.58 s | Passed |
| Source archive rebuilt and installed in a fresh environment | 5,663 / 25 | 965.57 s | Passed |

The [retained record](2026-11-08-artifact-qualification-d8bf94d.json) includes
the original hash-bound qualification receipt, artifact/helper/log hashes and
separate failed-attempt records. The source files and helper still match the
recorded commit. These are `0.4.1` development artifacts; no release publication,
tag or merge occurred. Changes after this commit require their own qualification.

The first artifact attempt passed the wheel profile but exhausted temporary
filesystem inodes during the source-archive profile: 3,204 passed, one failed,
nine setup errors and 25 skipped. It produced no qualification receipt. The
retry used temporary storage on the main filesystem and reran both profiles;
the earlier logs were archived before the helper replaced its working logs.

The complete source suite at this commit remains a failed attempt: 12,150 passed,
four failed, 20 setup errors and 34 skipped, with 91.36% coverage. Three CLI
subprocesses exceeded their unchanged ten-second limit; the other failure and
setup errors coincided with inode exhaustion. Focused reruns passed 27 CLI and
59 evaluation-fixture tests. Those reruns do not establish a passing full source
suite or prove why the CLI timeouts occurred.

This checkpoint extends the [earlier artifact record](2026-11-08-artifact-qualification.md).
Current native CI, final `0.4.2` artifacts, local model quality and human-facing
terminal/accessibility acceptance remain separate requirements under
[#30](https://github.com/mlg151/henchman-ai/issues/30).
