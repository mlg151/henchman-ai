# Installed-wheel task-stop check

A clean archive of commit `f5c9abd3b9ad1d5e8653c7301cbdf5e9975ddcc6` was
built offline as a Python wheel. Its source archive SHA-256 was
`b8f498a2530d8a03b2ee6e0035fb2d2a50489aca396c10d23775161be921db61`; the
wheel SHA-256 was
`f2e62e92413c75ac9125eeb09e3d4c975fafca6b2f8a912572e546dc7501103f`.
The version was still 0.4.1; this is not a release artifact.

The wheel was installed without dependencies into a fresh Python 3.11 virtual
environment. Its 454 package files matched the wheel bytes, and an isolated
interpreter confirmed that Henchman loaded from that environment. The staged
wheel-smoke tree then ran all **19 task-stop tests successfully**. Home and
XDG paths were private and network installation was disabled. Dependencies
were reused from the existing local development environment through a `.pth`
path, so this was not an independent dependency installation.

The first pytest invocation supplied `--no-cov` while plugin autoload was
disabled; pytest rejected that option before collection. The corrected
invocation, matching the wheel-smoke runner's plugin setup, passed. The wheel,
archive, environment and staged test tree remain in the local
release-qualification cache. This focused Linux observation does not replace
cross-platform CI or verification of the final release commit and artifacts.
