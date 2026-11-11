# Repository reuse paired experiment: synthetic preflight v2

This is an offline integration check for the
[paired experiment](../../evals/repository_reuse_paired_v1/README.md), not a
model evaluation. Scripted responses exercised the real fixture preparation,
search tools, scoped editing, verification and independent bounded oracle.
No endpoint or model was used, and this result does not establish that either
retrieval strategy improves task quality or completes issue #17.

The frozen source was commit `d195ac18d3c2d586e30f29f218c7813e97c97269`.
Its source manifest SHA-256 was
`4a65948a65ed6e1ce84babdf903b919baae37d500db86c83dfb5595c9a299832`;
all 1,751 tracked source entries, including four symlinks, matched it. The
21 harness scripts were checked against the preflight manifest. Forty-seven
focused fault and behavior checks passed on each of Python 3.11 and 3.12.

All 12 fixed attempts finished with the oracle accepting, a current correlated
verification after joined cleanup, and no guard or tool failures. The audit
checked all six pairs for matching fixture bytes, initial Git commit, settings,
task, system message and tool catalog; only the declared search evidence in the
user message differed. The 48 requests and their reported usage were synthetic.
The audit also checked worker identity settlement and hashed 790 retained raw
files. Its SHA-256 was
`53bf142c54b13997b86817f5493f424b05cedbe9bdef8db3f1f1069cfca7d181`.

This version rejects parent traversal before path normalization, including a
symlink-plus-`..` case. The preceding preflight remains separate because it
used the earlier guard. Both preflights and the raw v2 files are retained in the
local release-qualification cache; the repository scripts and source manifest
are sufficient to reconstruct the frozen inputs. The guard is cooperative and
is not a general filesystem sandbox. The finite, harness-defined oracle can
reject unsupported but correct programs and can share errors with its fixtures.
