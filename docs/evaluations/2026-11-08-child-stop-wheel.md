# Installed-wheel work interruption check

A clean archive of commit `be6ad0554077ac337fd93ad5606025d71617830f` was
built offline as a Python wheel. Its source archive SHA-256 was
`b2920fe52d4b99f1b747aa7da968dc46f09e5850dd4d669864e3241f52e19c63`;
the wheel SHA-256 was
`694fcdabe02bb9d2e1102e29ab40fa0379f2c5142ea2dd6ffb1fa3809c72d3de`.
The version was still 0.4.1; this is not a release artifact.

The wheel was installed without dependencies into a fresh Python 3.11 virtual
environment. All 454 package files matched the wheel bytes. The staged tests
asserted that Henchman loaded from the installed distribution and ran all
**35 child-agent and task interruption tests successfully**; an independently
captured repeat also passed 35/35. Home and XDG paths were private, and the
wheel and its build requirements were obtained offline. Existing local
development dependencies were reused via a `.pth` path, so dependency
installation was not independently qualified.

The first launcher could not find `python` and ran no build. A subsequent
`python3` launch built the wheel but its system Python 3.14 could not create a
virtual environment because `ensurepip` was unavailable; no tests ran in that
attempt. The corrected attempt used the existing Python 3.11 interpreter and
an offline `uv` environment. The wheel, archive, staged tree, environment and
repeat log remain in the local release-qualification cache. This focused Linux
observation does not replace native cross-platform CI or verification of the
final release commit and artifacts.

## Later tree-cleanup refusal check

After adding refusal for a selected child or descendant already in cancellation
cleanup, a separate clean archive of commit
`702760edf4891f11bef08a549ed98cf1b21072fa` was built offline. The archive
SHA-256 was `016e9b5eaaaf409f2e811e12af593f51840bb41bde51b455c67cdc1192f825f1`;
the wheel SHA-256 was
`0c0650de587dec5e838907b99f4c409f5f51e159a0bf338e149eddd9cd8abbc7`.
In a fresh Python 3.11 environment, all 454 package files matched the wheel and
**37/37 staged interruption tests passed**, including both new cleanup cases.
The same local dependency reuse and release-qualification limits above apply.
The separate archive, wheel, staged tree and test log are retained under the
`child-stop-wheel-702760e` qualification-cache directory.
