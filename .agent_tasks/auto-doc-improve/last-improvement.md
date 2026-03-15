# Last Documentation Improvement

## Date/Time
2026-03-15T02:00:00Z (approximate)

## Files Changed
- `.github/copilot-instructions.md`

## Smell Category Addressed
Accuracy (HIGH severity)

## Rationale for Change
The "Available Providers" table in the copilot instructions was inaccurate for several providers. The table showed "Default Model" values for providers that don't actually have hardcoded default models, which could mislead users into thinking these models would be used automatically when they actually need to be explicitly configured.

Specifically:
- `openai_compat` (generic OpenAI-compatible provider) was shown with default model `gpt-4o`, but it's a generic provider that requires explicit model configuration
- `together`, `groq`, and `fireworks` (aliases for `openai_compat`) were shown with specific default models, but they're just aliases that also require explicit model configuration

Only DeepSeek, Anthropic, Ollama, and OpenRouter have actual hardcoded default models in their provider implementations.

## Changes Made
1. **Updated `.github/copilot-instructions.md`**:
   - Changed the "Default Model" column for providers without hardcoded defaults from specific model names to "(config required)"
   - Added a note explaining that providers marked "(config required)" do not have hardcoded default models and must be configured explicitly
   - Affected providers:
     - OpenAI-Compatible (`openai_compat`): Changed from `gpt-4o` to `(config required)`
     - Together AI (`together`): Changed from `meta-llama/Llama-3.3-70B-Instruct-Turbo` to `(config required)`
     - Groq (`groq`): Changed from `llama-3.3-70b-specdec` to `(config required)`
     - Fireworks AI (`fireworks`): Changed from `accounts/fireworks/models/llama-v3p1-70b-instruct` to `(config required)`

## What to Verify
- The copilot instructions now accurately reflect which providers have hardcoded default models vs. those that require explicit configuration
- The change doesn't break any formatting or links in the file
- The actual provider implementations match the documentation:
  - DeepSeek: `deepseek-chat` (correct)
  - Anthropic: `claude-sonnet-4-20250514` (correct)
  - Ollama: `llama3.2` (correct)
  - OpenRouter: `openai/gpt-4o-mini` (correct)
  - OpenAI-Compatible, Together, Groq, Fireworks: No hardcoded defaults (correct)
- The added explanatory note is clear and helpful

## Next Priority
All documentation smells have been addressed with a perfect score of 100.0/100. Future documentation improvements should focus on:
1. Keeping the copilot instructions synchronized with actual project features
2. Ensuring example lists in documentation are representative of the full capabilities
3. Proactively updating internal guidance files when new tools or providers are added
4. Periodically verifying that documented defaults match actual code implementations
5. Ensuring consistency between different documentation files (copilot instructions, README, docs/)