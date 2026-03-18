# Four Lenses Bug Report: src/henchman/cli/textual_mixins.py
## Date: 2025-03-18T14:00:00Z
## Bug Summary
The `_NullProvider.chat_completion_stream` method has an unreachable `yield` statement inside `if False:` that makes the function appear to be a generator but will never actually yield, causing type checking issues and potential runtime confusion.

## Lens
**Phase 1: The Intent vs. Reality Check** - Logic Gaps

## Expected vs. Observed
| Expected Behavior | Observed Risk |
|---|---|
| `_NullProvider.chat_completion_stream` should either properly implement the async generator interface or raise an error without pretending to be a generator | The method has `if False: yield StreamChunk()` which creates an unreachable code path that makes static analysis tools think it's a generator when it's not |
| Type checkers should see the method returns `AsyncIterator[StreamChunk]` | The unreachable `yield` tricks type checkers into thinking it's a valid generator |
| The method should clearly communicate it cannot stream | The `if False:` construct is a hack that obscures the actual behavior |

## Root Cause
The `_NullProvider` class is a fallback provider that raises `RuntimeError` when used. The `chat_completion_stream` method needs to be an async generator (returning `AsyncIterator[StreamChunk]`) to satisfy the `ModelProvider` interface, but it never actually yields anything - it only raises an exception. The developer added `if False: yield StreamChunk()` to make the function syntactically an async generator, but this creates dead code and confuses both humans and tools.

## Fix Plan
Remove the `if False:` guard and the unreachable `yield` statement. Instead, make the method a proper async generator that immediately raises the `RuntimeError`. This can be done by either:
1. Keeping it as an async generator with `async def` and `raise` (which is valid Python)
2. Or restructuring to avoid the unreachable code

## Status: IN PROGRESS