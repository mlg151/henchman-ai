# Last Documentation Improvement

## Date/Time
2026-03-15T08:10:00Z (approximate)

## Files Changed
1. `docs/providers.md` - Removed redundant "OpenAI (via `openai_compat`)" row from providers table

## Smell Category Addressed
Accuracy (Inconsistent provider documentation)

## Rationale for Change
The providers.md documentation table contained a redundant row for "OpenAI (via `openai_compat`)" that was inconsistent with:
1. The actual provider registry implementation (which doesn't have a separate `openai` provider)
2. The index.md documentation (which doesn't list OpenAI as a separate provider)
3. The getting-started.md documentation (which correctly explains OpenAI is used via `openai_compat` with specific base URL)

**Before (inconsistent)**:
- Table had "OpenAI (via `openai_compat`)" as a separate row, suggesting it's a distinct provider
- This created confusion because `openai_compat` is the actual provider name, and OpenAI is just one configuration of it
- Inconsistent with index.md which doesn't have this separate row

**After (consistent)**:
- Table now only lists actual registered providers: `deepseek`, `anthropic`, `ollama`, `openrouter`, `openai_compat`, `together`, `groq`, `fireworks`
- The note already explains: "For OpenAI specifically, use `openai_compat` with `base_url: https://api.openai.com/v1` and `api_key: ${OPENAI_API_KEY}`."
- Consistent with index.md and getting-started.md documentation
- Matches the actual provider registry implementation

## Verification Performed
1. ✅ **Registry check**: Verified that `src/henchman/providers/registry.py` only registers `deepseek`, `anthropic`, `ollama`, `openrouter`, `openai_compat`, `together`, `groq`, `fireworks` (no separate `openai` provider)
2. ✅ **Consistency check**: Verified index.md doesn't have separate OpenAI row, only lists `openai_compat` as generic provider
3. ✅ **Getting-started check**: Verified getting-started.md correctly explains OpenAI is used via `openai_compat` with specific base URL
4. ✅ **Note clarity**: The note in providers.md already clearly explains how to use OpenAI with `openai_compat`
5. ✅ **Cross-reference check**: No other documentation files reference "OpenAI (via `openai_compat`)" as a separate provider

## What to Verify
1. ✅ **Provider registry**: Only the 8 providers listed are actually registered
2. ✅ **Documentation consistency**: All documentation files now have consistent messaging about OpenAI usage
3. ✅ **User clarity**: Users won't be confused into looking for a separate `openai` provider
4. ✅ **Configuration examples**: The examples in providers.md show how to configure `openai_compat` for different services including OpenAI

## Impact
- **Low risk**: Documentation change only, no code changes
- **High value**: Eliminates potential user confusion about provider naming
- **Consistency**: Aligns documentation with actual implementation and across all documentation files
- **Clarity**: Makes it clear that `openai_compat` is the provider name, and OpenAI is one of many services that can be used with it

## Next Priority
While the documentation smell report shows a perfect score (100.0/100), subtle inconsistencies like this one may not be caught by automated checks. Future documentation reviews should:
1. Check for consistency between different documentation files (index.md, providers.md, getting-started.md)
2. Verify documentation matches actual code implementation (provider registry)
3. Look for redundant or misleading information in tables
4. Ensure examples in documentation match the described behavior
5. Check that all registered providers are documented, and no non-existent providers are documented