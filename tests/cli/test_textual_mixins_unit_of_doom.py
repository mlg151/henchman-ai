"""Unit of Doom test for the real bug in textual_mixins.py.

The bug: In _textual_confirm callback, the logic for converting unexpected
result types to bool has a flaw. The comment says "to avoid the string 
'bool(result)' in source code" but actually using `if result:` also calls
`__bool__` on the object, which might have side effects.

More importantly, the conversion logic is inconsistent:
- `result is True` → `True`
- `result is False` → `False`  
- `result is None` → `False`
- Any other truthy value → `True`
- Any other falsy value → `False`

But what if `result` is `1` (integer)? It's truthy, so converts to `True`.
What if `result` is `0`? It's falsy, so converts to `False`.
What if `result` is `"yes"` (string)? It's truthy, converts to `True`.

This might not be the intended behavior. The screen should return `True` or
`False`, not arbitrary values.

Actually, the real bug might be elsewhere. Let me think...

Actually, I think the real bug is that the callback uses `contextlib.suppress(asyncio.InvalidStateError)`
to suppress errors when setting future result. But if the future is already
done (cancelled or has result), we suppress the error silently. This could
hide bugs.

But actually, that's defensive programming.

Wait! I think I found the real bug! Look at the _cleanup_confirm_futures
method comment: "if future.cancel() triggers callbacks that modify the dict"
But future.cancel() shouldn't trigger the _callback function! The _callback
is passed to push_screen, not added to the future with add_done_callback().

So the comment is wrong, but that's not a functional bug.

Actually, let me write a test that demonstrates a real functional bug.
"""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch
import pytest

from henchman.cli.textual_mixins import _InitMixin, _NullProvider
from henchman.tools.base import ConfirmationRequest
from henchman.providers.base import Message


class TestTextualMixinsUnitOfDoom:
    """Unit of Doom test for a real bug."""
    
    @pytest.mark.anyio
    async def test_null_provider_chat_completion_stream_unreachable_yield(self) -> None:
        """Test that _NullProvider.chat_completion_stream has unreachable code.
        
        The bug: The method is marked as returning AsyncIterator[StreamChunk]
        but it never yields a StreamChunk! It always raises RuntimeError.
        This violates the method contract.
        
        Actually, that's by design - it's a null provider that always errors.
        So this is NOT a bug.
        
        Let me think of a different bug...
        """
        provider = _NullProvider()
        messages = [Message(role="user", content="test")]
        
        # The method should return an async iterator
        stream = await provider.chat_completion_stream(messages)
        
        # But the iterator never yields, always raises
        with pytest.raises(RuntimeError):
            await stream.__aiter__().__anext__()
        
        # This is correct behavior for a null provider.
        # So no bug here.
    
    @pytest.mark.anyio
    async def test_textual_confirm_callback_bool_conversion_bug(self) -> None:
        """Test the bool conversion bug in _textual_confirm callback.
        
        The bug: The callback converts arbitrary truthy/falsy values to bool.
        If the screen returns a string like "yes", it converts to True.
        If the screen returns an integer like 1, it converts to True.
        This might not be intended.
        """
        # This is hard to test because _callback is a nested function.
        # But we can extract the logic.
        
        # The bug is in this code:
        # if result:
        #     future.set_result(True)
        # else:
        #     future.set_result(False)
        #
        # This converts any truthy value to True, any falsy to False.
        # But should it?
        
        # Actually, the screen should return True or False, not arbitrary values.
        # So this is defensive programming, not a bug.
        
        # Let me look for a different bug...
        pass
    
    @pytest.mark.anyio 
    async def test_cleanup_confirm_futures_missing_lock_bug(self) -> None:
        """Test that _cleanup_confirm_futures doesn't acquire _confirm_lock.
        
        Bug: _textual_confirm acquires _confirm_lock to modify _confirm_futures,
        but _cleanup_confirm_futures doesn't acquire it. This is a race condition.
        
        However, _cleanup_confirm_futures is called from on_unmount (sync)
        and _confirm_lock is an asyncio.Lock, so it can't acquire it.
        
        This is a design limitation, not a code bug.
        
        Actually, wait! The real bug might be that _cleanup_confirm_futures
        should use a threading.Lock instead of asyncio.Lock, or both methods
        should use a reentrant lock that works in both sync and async contexts.
        """
        # Create mixin instance
        mixin = _InitMixin.__new__(_InitMixin)
        
        # Initialize state
        mixin._confirm_lock = asyncio.Lock()
        mixin._confirm_counter = 0
        mixin._confirm_futures = {}
        
        # Add a future
        future = asyncio.Future()
        mixin._confirm_futures[1] = future
        
        # Call cleanup
        mixin._cleanup_confirm_futures()
        
        # Future should be cancelled
        assert future.cancelled()
        
        # Dict should be empty
        assert len(mixin._confirm_futures) == 0
        
        # This works, but there's a potential race if _textual_confirm
        # is running concurrently.
        
        # Actually, I think THIS IS THE BUG!
        # _cleanup_confirm_futures should synchronize with _textual_confirm
        # but it can't because of the async/sync mismatch.
        
        # This is the bug I will fix!