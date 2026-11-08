# Staged delegation local pilot snapshots

The `.py.txt` files are exact copies of the scripts used for the three attempts
documented in the [pilot report](../../docs/evaluations/2026-11-08-staged-local-pilot.md).
They are evidence snapshots, not a general evaluation runner. Their SHA-256
digests are recorded in the [summary](../../docs/evaluations/2026-11-08-staged-local-pilot.json).

They make local model requests if executed. Each requires a new private
`PILOT_ROOT` containing empty `home` and `project` directories, an already
running matching model at the fixed localhost endpoint, and the exact tested
package environment. They contain a fixed dummy local API credential and deny
other provider destinations. The scripts do not prove isolation of unrelated
process traffic or exclusive access to the shared local server.
