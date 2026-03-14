# Last Documentation Improvement

## Date/Time
2026-03-14T20:15:00Z (approximate)

## Files Changed
- `CHANGELOG.md` (root file)
- `docs/CHANGELOG.md` (already correct, verified)

## Smell Category Addressed
Consistency Error (HIGH severity)

## Rationale for Change
Fixed a critical documentation inconsistency between the project's version tracking. The root `CHANGELOG.md` file incorrectly listed version `0.3.14` with a release date (2026-03-10) while:
1. The source code `version.py` shows version `0.3.13`
2. Git tags show `v0.3.13` as the latest tag
3. According to Keep a Changelog format, released versions should have dates and unreleased changes should be under `[Unreleased]`

This inconsistency would confuse users about what version is actually released and what features are available in the current version.

## Changes Made
1. **Root CHANGELOG.md**:
   - Moved all `0.3.14` content from the `## [0.3.14] - 2026-03-10` section to the `## [Unreleased]` section
   - Removed the `## [0.3.14] - 2026-03-10` header entirely
   - Updated the comparison link at the bottom from `[Unreleased]: https://github.com/mlg151/henchman-ai/compare/v0.3.14...HEAD` to `[Unreleased]: https://github.com/mlg151/henchman-ai/compare/v0.3.13...HEAD`
   - Removed the `[0.3.14]: https://github.com/mlg151/henchman-ai/compare/v0.3.13...v0.3.14` link

2. **Verified docs/CHANGELOG.md**:
   - Already had the correct structure with changes under `[Unreleased]`
   - Already had the correct comparison link `[Unreleased]: https://github.com/mlg151/henchman-ai/compare/v0.3.13...HEAD`
   - No changes needed to this file

## What to Verify
- The CHANGELOG now correctly follows Keep a Changelog format
- All changes that were under `0.3.14` are now properly under `[Unreleased]`
- The version in `src/henchman/version.py` (0.3.13) matches the latest released version in CHANGELOG
- Git tags show `v0.3.13` as the latest tag
- The comparison links at the bottom of CHANGELOG.md are correct
- No breaking changes to source code functionality
- Documentation accurately reflects the actual project state

## Next Priority
All documentation smells have been addressed. The project now has a perfect documentation score of 100.0/100 with no remaining smells. Future documentation improvements should focus on:
1. Keeping the CHANGELOG synchronized with actual releases
2. Ensuring version numbers match between source code, git tags, and documentation
3. Proactively updating documentation when new features are added