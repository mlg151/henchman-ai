# Documentation Improvement Record

## Date/Time
2026-02-27T14:50:00Z

## Files Changed
1. `mkdocs.yml` - Updated GitHub repository URLs from 'matthew/henchman-ai' to 'mlg151/henchman-ai'
2. `docs/getting-started.md` - Updated git clone URL from 'matthew/henchman-ai' to 'mlg151/henchman-ai'
3. `docs/index.md` - Updated LICENSE link from 'matthew/henchman-ai' to 'mlg151/henchman-ai'
4. `CONTRIBUTING.md` - Fixed placeholder GitHub URL and updated class references

## Smell Category Addressed
- **Consistency Error** (CRITICAL): Standardized GitHub repository URLs across all documentation files
- **Consistency Error** (HIGH): Fixed placeholder GitHub URL in CONTRIBUTING.md
- **Stale Content** (HIGH): Updated 'BaseProvider' to 'ModelProvider' and 'BaseTool' to 'Tool' in CONTRIBUTING.md

## Rationale for Change
The documentation had inconsistent GitHub repository URLs, with some files referencing 'matthew/henchman-ai' while most files (including pyproject.toml, README.md, CHANGELOG.md) referenced 'mlg151/henchman-ai'. This violates the **CONSISTENCY** principle - all references to external resources should be uniform.

Additionally, CONTRIBUTING.md had stale class references ('BaseProvider' and 'BaseTool') that don't exist in the codebase, violating the **ACCURACY** principle - documentation must match the actual code.

## Changes Made
1. **mkdocs.yml**: Updated `site_url`, `repo_name`, `repo_url`, and social link to use 'mlg151/henchman-ai'
2. **docs/getting-started.md**: Updated git clone command to use correct repository
3. **docs/index.md**: Updated LICENSE link to point to correct repository
4. **CONTRIBUTING.md**: 
   - Added clarification to git clone command that contributors should replace 'your-username'
   - Updated 'BaseProvider' to 'ModelProvider' (actual class name)
   - Updated 'BaseTool' to 'Tool' (actual class name)

## What to Verify
1. Run `mkdocs serve` to ensure all GitHub links work correctly
2. Check that the git clone command in getting-started.md works
3. Verify that the LICENSE link resolves correctly
4. Confirm that the class names in CONTRIBUTING.md match the actual source code

## Next Priority
The next highest-priority issue is **Stale Content** in `docs/tools.md` - many tools exist in source but are not documented. The tools.md file has 29 smells and needs comprehensive updating to include all available tools.