# Four Lenses Bug Report: src/henchman/cli/textual_mixins.py
## Date: 2025-03-17T20:00:00Z
## Bug Summary
The `_NullProvider.chat_completion_stream` method has unreachable dead code: a `yield` statement that comes after a `raise` statement, making it impossible to execute.

## Lens
**Phase 1: The Intent vs. Reality Check** - Logic Gaps

## Expected vs. Observed
| Expected Behavior | Observed Risk |
|---|---|
| Method should either properly implement async generator or not have unreachable code | Unreachable `yield` statement after `raise` creates dead code that can confuse developers and static analysis tools |
| Code should be maintainable and follow Python best practices | Dead code violates "once and only once" principle and creates maintenance burden |
| Type hints should match implementation | Method returns `AsyncIterator[StreamChunk]` but raises exception instead of yielding |

## Root Cause
The method `chat_completion_stream` in `_NullProvider` class raises a `RuntimeError` immediately, but then has a `yield` statement that can never be reached. The `if False:` guard attempts to make it "reachable" for type checking, but the `raise` statement before it makes the entire `if False:` block unreachable.

## Fix Plan
Remove the unreachable `yield` statement and restructure the method to either:
1. Make the `yield` actually reachable (inside the `if False:` block before the `raise`)
2. Remove the `yield` entirely and handle type checking differently
3. Restructure to be a proper async generator that yields nothing then raises

Option 1 is simplest: move the `raise` statement after the `if False:` block, or put the `yield` in a truly reachable position.

## Status: IN PROGRESS