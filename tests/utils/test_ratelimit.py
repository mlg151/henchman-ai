"""Comprehensive tests for AsyncRateLimiter class."""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from henchman.utils.ratelimit import AsyncRateLimiter


class TestAsyncRateLimiter:
    """Test suite for AsyncRateLimiter class."""

    def test_initialization(self) -> None:
        """Test that AsyncRateLimiter initializes correctly."""
        # Test with different token limits
        limiter = AsyncRateLimiter(tokens_per_minute=100)
        assert limiter.tokens_per_minute == 100
        assert len(limiter.usage) == 0
        assert hasattr(limiter, "_lock")

        limiter2 = AsyncRateLimiter(tokens_per_minute=500)
        assert limiter2.tokens_per_minute == 500
        assert len(limiter2.usage) == 0

    def test_get_current_usage_empty(self) -> None:
        """Test _get_current_usage with empty deque."""
        limiter = AsyncRateLimiter(tokens_per_minute=100)
        assert limiter._get_current_usage() == 0

    def test_get_current_usage_with_entries(self) -> None:
        """Test _get_current_usage with entries in deque."""
        limiter = AsyncRateLimiter(tokens_per_minute=100)

        # Mock time to control test
        with patch("time.time") as mock_time:
            mock_time.return_value = 1000.0
            limiter.usage.append((1000.0, 10))
            limiter.usage.append((1000.5, 20))
            limiter.usage.append((1000.8, 15))

            assert limiter._get_current_usage() == 45  # 10 + 20 + 15

    @pytest.mark.asyncio
    async def test_clean_old_usage_empty(self) -> None:
        """Test _clean_old_usage with empty deque."""
        limiter = AsyncRateLimiter(tokens_per_minute=100)

        with patch("time.time") as mock_time:
            mock_time.return_value = 1000.0
            await limiter._clean_old_usage()
            assert len(limiter.usage) == 0

    @pytest.mark.asyncio
    async def test_clean_old_usage_all_old(self) -> None:
        """Test _clean_old_usage removes entries older than 60 seconds."""
        limiter = AsyncRateLimiter(tokens_per_minute=100)

        # Add old entries (more than 60 seconds old)
        limiter.usage.append((900.0, 10))  # 100 seconds old
        limiter.usage.append((920.0, 20))  # 80 seconds old
        limiter.usage.append((950.0, 15))  # 50 seconds old (should keep)
        limiter.usage.append((980.0, 25))  # 20 seconds old (should keep)

        with patch("time.time") as mock_time:
            mock_time.return_value = 1000.0  # Current time
            await limiter._clean_old_usage()

            # Only entries from 940.0 and newer should remain
            assert len(limiter.usage) == 2
            assert limiter.usage[0] == (950.0, 15)
            assert limiter.usage[1] == (980.0, 25)

    @pytest.mark.asyncio
    async def test_clean_old_usage_mixed_ages(self) -> None:
        """Test _clean_old_usage with mixed old and new entries."""
        limiter = AsyncRateLimiter(tokens_per_minute=100)

        # Add entries with various ages
        limiter.usage.append((935.0, 5))  # 65 seconds old (remove)
        limiter.usage.append((945.0, 10))  # 55 seconds old (keep)
        limiter.usage.append((955.0, 15))  # 45 seconds old (keep)
        limiter.usage.append((965.0, 20))  # 35 seconds old (keep)

        with patch("time.time") as mock_time:
            mock_time.return_value = 1000.0
            await limiter._clean_old_usage()

            assert len(limiter.usage) == 3
            assert limiter.usage[0] == (945.0, 10)
            assert limiter.usage[1] == (955.0, 15)
            assert limiter.usage[2] == (965.0, 20)

    @pytest.mark.asyncio
    async def test_add_usage_basic(self) -> None:
        """Test basic add_usage functionality."""
        limiter = AsyncRateLimiter(tokens_per_minute=100)

        with patch("time.time") as mock_time:
            mock_time.return_value = 1000.0
            await limiter.add_usage(10)

            assert len(limiter.usage) == 1
            assert limiter.usage[0] == (1000.0, 10)

    @pytest.mark.asyncio
    async def test_add_usage_multiple_calls(self) -> None:
        """Test multiple add_usage calls."""
        limiter = AsyncRateLimiter(tokens_per_minute=100)

        with patch("time.time") as mock_time:
            mock_time.side_effect = [1000.0, 1000.5, 1001.0]

            await limiter.add_usage(10)
            await limiter.add_usage(20)
            await limiter.add_usage(15)

            assert len(limiter.usage) == 3
            assert limiter.usage[0] == (1000.0, 10)
            assert limiter.usage[1] == (1000.5, 20)
            assert limiter.usage[2] == (1001.0, 15)

    @pytest.mark.asyncio
    async def test_wait_for_capacity_immediate(self) -> None:
        """Test wait_for_capacity when capacity is immediately available."""
        limiter = AsyncRateLimiter(tokens_per_minute=100)

        with patch("time.time") as mock_time:
            mock_time.return_value = 1000.0

            # Mock asyncio.sleep to ensure it's not called
            with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
                await limiter.wait_for_capacity(50)

                # Should not sleep since capacity is available
                mock_sleep.assert_not_called()

    @pytest.mark.asyncio
    async def test_wait_for_capacity_needs_wait(self) -> None:
        """Test wait_for_capacity when it needs to wait for capacity."""
        limiter = AsyncRateLimiter(tokens_per_minute=100)

        # Add some usage first
        with patch("time.time") as mock_time:
            mock_time.return_value = 1000.0
            await limiter.add_usage(80)  # Use 80 tokens

        # Now try to use 30 more tokens (total would be 110 > 100)
        with patch("time.time") as mock_time:
            mock_time.side_effect = [1000.0, 1000.0, 1060.1]  # Time progression

            with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
                # Create a task to run wait_for_capacity
                task = asyncio.create_task(limiter.wait_for_capacity(30))

                # Give it a moment to start
                await asyncio.sleep(0)

                # Should call sleep to wait for oldest entry to expire
                mock_sleep.assert_called_once()

                # Simulate time passing and cleanup
                await task

    @pytest.mark.asyncio
    async def test_wait_for_capacity_tokens_exceed_limit(self) -> None:
        """Test wait_for_capacity when requested tokens exceed limit."""
        limiter = AsyncRateLimiter(tokens_per_minute=100)

        # Request more tokens than the limit (should be capped to limit)
        with patch("time.time") as mock_time:
            mock_time.return_value = 1000.0

            with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
                # Test with tokens > limit
                await limiter.wait_for_capacity(150)  # > 100 limit

                # Should have been capped to tokens_per_minute (100)
                # Since there's no existing usage, it should complete immediately
                # without sleeping
                mock_sleep.assert_not_called()

        # Also test with existing usage
        limiter2 = AsyncRateLimiter(tokens_per_minute=100)
        # Add some usage
        with patch("time.time") as mock_time:
            mock_time.return_value = 1000.0
            await limiter2.add_usage(50)

        # Now request more than limit
        with (
            patch("time.time") as mock_time,
            patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep,
        ):
            # Need enough time calls for:
            # 1. _clean_old_usage() call 1
            # 2. sleep_time calculation
            # 3. _clean_old_usage() call 2 (after sleep)
            mock_time.side_effect = [1000.0, 1000.0, 1060.1, 1060.1]

            # Request 150 tokens (> 100 limit)
            await limiter2.wait_for_capacity(150)

            # Should wait for window to clear (capped to 100 tokens)
            # Since we have 50 tokens used, need to wait for them to expire
            # to get 100 tokens available
            mock_sleep.assert_called()

    @pytest.mark.asyncio
    async def test_wait_for_capacity_empty_deque_edge_case(self) -> None:
        """Test wait_for_capacity edge case with empty deque but current_usage > 0."""
        limiter = AsyncRateLimiter(tokens_per_minute=100)

        # This tests the else branch in wait_for_capacity
        # where self.usage is empty but current_usage > 0
        # This shouldn't happen in practice but is covered in code

        # Create an AsyncMock that returns an awaitable
        mock_sleep = AsyncMock(return_value=None)

        # We need _get_current_usage to return 50 first, then 0 after sleep
        # to break out of the loop
        usage_values = [50, 0]

        def get_current_usage_side_effect():
            return usage_values.pop(0) if usage_values else 0

        with (
            patch("time.time") as mock_time,
            patch.object(limiter, "_clean_old_usage"),
            patch.object(limiter, "_get_current_usage", side_effect=get_current_usage_side_effect),
            patch("asyncio.sleep", mock_sleep),
        ):
            mock_time.return_value = 1000.0

            # Call wait_for_capacity
            await limiter.wait_for_capacity(60)

            # Should have called sleep with 1 second (else branch)
            mock_sleep.assert_called_once_with(1)

    @pytest.mark.asyncio
    async def test_concurrent_access(self) -> None:
        """Test that concurrent access is properly serialized by lock."""
        limiter = AsyncRateLimiter(tokens_per_minute=100)

        results = []

        async def add_usage_task(token_count: int, delay: float = 0) -> None:
            """Task to add usage with optional delay."""
            if delay > 0:
                await asyncio.sleep(delay)
            await limiter.add_usage(token_count)
            results.append(token_count)

        # Run multiple tasks concurrently
        with patch("time.time") as mock_time:
            mock_time.side_effect = [1000.0, 1000.1, 1000.2, 1000.3]

            tasks = [
                add_usage_task(10, 0.1),
                add_usage_task(20, 0),
                add_usage_task(15, 0.05),
            ]

            await asyncio.gather(*tasks)

            # All tasks should complete
            assert len(results) == 3
            assert len(limiter.usage) == 3
            # Usage should be in order of completion (serialized by lock)
            # Note: actual order depends on event loop scheduling

    @pytest.mark.asyncio
    async def test_integration_flow(self) -> None:
        """Test integrated flow of wait_for_capacity and add_usage."""
        limiter = AsyncRateLimiter(tokens_per_minute=100)

        with patch("time.time") as mock_time:
            # Start at time 1000
            mock_time.side_effect = [
                1000.0,  # add_usage(40)
                1000.0,  # wait_for_capacity(70) - check 1
                1000.0,  # wait_for_capacity(70) - check 2 (after sleep)
                1060.1,  # after sleep
                1060.1,  # add_usage(70)
            ]

            # Add initial usage
            await limiter.add_usage(40)
            assert len(limiter.usage) == 1

            # Now wait for capacity for 70 more tokens
            # Total would be 110 > 100, so need to wait
            with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
                # Start wait_for_capacity
                wait_task = asyncio.create_task(limiter.wait_for_capacity(70))

                # Give it a moment
                await asyncio.sleep(0)

                # Should have called sleep
                assert mock_sleep.called

                # Complete the task
                await wait_task

            # Now add the usage
            await limiter.add_usage(70)
            # After waiting, the old usage (1000.0) should have been cleaned
            # since we advanced time to 1060.1 (> 60 seconds later)
            # So we should only have the new usage
            assert len(limiter.usage) == 1
            assert limiter.usage[0] == (1060.1, 70)

    @pytest.mark.asyncio
    async def test_cleanup_integration(self) -> None:
        """Test that cleanup happens during wait_for_capacity."""
        limiter = AsyncRateLimiter(tokens_per_minute=100)

        # Add old usage
        limiter.usage.append((900.0, 50))  # 100 seconds old at time 1000

        with patch("time.time") as mock_time:
            mock_time.return_value = 1000.0

            # Wait for capacity - should trigger cleanup
            with patch("asyncio.sleep", new_callable=AsyncMock):
                await limiter.wait_for_capacity(60)

                # Old usage should have been cleaned
                assert len(limiter.usage) == 0

    @pytest.mark.asyncio
    async def test_zero_tokens(self) -> None:
        """Test edge case with zero tokens."""
        limiter = AsyncRateLimiter(tokens_per_minute=100)

        with patch("time.time") as mock_time:
            mock_time.return_value = 1000.0

            # Should complete immediately
            await limiter.wait_for_capacity(0)

            # Add zero usage
            await limiter.add_usage(0)
            assert len(limiter.usage) == 1
            assert limiter.usage[0] == (1000.0, 0)

    @pytest.mark.asyncio
    async def test_negative_time_edge_case(self) -> None:
        """Test edge case with negative sleep time calculation."""
        limiter = AsyncRateLimiter(tokens_per_minute=100)

        # Add recent usage
        limiter.usage.append((1000.0, 80))

        with patch("time.time") as mock_time:
            # Current time is already past expiration
            mock_time.side_effect = [1060.5, 1060.5]  # 60.5 seconds after usage

            with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
                await limiter.wait_for_capacity(30)

                # Should not sleep if sleep_time <= 0
                # The implementation checks if sleep_time > 0
                mock_sleep.assert_not_called()

    @pytest.mark.asyncio
    async def test_sleep_time_zero_or_negative(self) -> None:
        """Test the branch where sleep_time <= 0 (oldest entry already expired)."""
        limiter = AsyncRateLimiter(tokens_per_minute=100)

        # Add usage that's exactly 60 seconds old (or slightly older)
        # sleep_time = 1000.0 + 60.1 - 1060.1 = 0.0
        limiter.usage.append((1000.0, 80))

        with (
            patch("time.time") as mock_time,
            patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep,
        ):
            # Current time is exactly at expiration boundary
            mock_time.side_effect = [1060.1, 1060.1]

            # Try to use more tokens
            await limiter.wait_for_capacity(30)

            # Should not sleep since sleep_time <= 0
            mock_sleep.assert_not_called()

            # The old usage should have been cleaned by _clean_old_usage
            # which is called at the start of each loop iteration
            # So current_usage should be 0 after cleanup
            # and wait_for_capacity should complete immediately

    @pytest.mark.asyncio
    async def test_lock_prevents_race_conditions(self) -> None:
        """Test that lock prevents race conditions in concurrent operations."""
        limiter = AsyncRateLimiter(tokens_per_minute=100)

        call_count = {"add": 0, "wait": 0}

        async def concurrent_operation(op_type: str) -> None:
            """Simulate concurrent operation."""
            if op_type == "add":
                await limiter.add_usage(10)
                call_count["add"] += 1
            else:
                await limiter.wait_for_capacity(10)
                call_count["wait"] += 1

        # Run many concurrent operations
        tasks = []
        for i in range(10):
            tasks.append(concurrent_operation("add" if i % 2 == 0 else "wait"))

        with patch("time.time") as mock_time:
            mock_time.return_value = 1000.0

            with patch("asyncio.sleep", new_callable=AsyncMock):
                await asyncio.gather(*tasks)

                # All operations should complete
                assert call_count["add"] == 5
                assert call_count["wait"] == 5
                # No exceptions should be raised

    @pytest.mark.asyncio
    async def test_multiple_loop_iterations_with_expired_entries(self) -> None:
        """Test case where sleep_time <= 0 but we still need to loop multiple times."""
        limiter = AsyncRateLimiter(tokens_per_minute=100)

        # Add multiple usage entries, some expired, some not
        # This tests the branch where sleep_time <= 0 but we still loop
        limiter.usage.append((900.0, 40))  # Expired (100 seconds old)
        limiter.usage.append((950.0, 40))  # Expired (50 seconds old)
        limiter.usage.append((980.0, 40))  # Not expired (20 seconds old)
        # Total usage in window: 40 (only the last entry)
        # But we need 70 tokens

        with (
            patch("time.time") as mock_time,
            patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep,
        ):
            # First call: time is 1000.0
            # sleep_time = 980.0 + 60.1 - 1000.0 = 40.1 > 0
            # So we should sleep
            mock_time.return_value = 1000.0

            # Start wait_for_capacity
            task = asyncio.create_task(limiter.wait_for_capacity(70))

            # Give it a moment
            await asyncio.sleep(0)

            # Should have called sleep
            mock_sleep.assert_called_once()

            # Now simulate time passing to 1040.2 (after sleep)
            # All entries are now expired
            mock_time.return_value = 1040.2

            # Complete the task
            await task

            # After sleep, all entries should be cleaned
            # and wait_for_capacity should complete

    @pytest.mark.asyncio
    async def test_sleep_time_less_than_or_equal_zero_branch(self) -> None:
        """Test the branch where sleep_time <= 0 (branch 58->48)."""
        limiter = AsyncRateLimiter(tokens_per_minute=100)

        # Add an expired entry
        limiter.usage.append((1000.0, 80))  # Expired at time >= 1060.0

        # Mock _clean_old_usage to NOT clean the entry
        # This simulates a race condition or edge case
        with (
            patch.object(limiter, "_clean_old_usage") as mock_clean,
            patch("time.time") as mock_time,
            patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep,
        ):
            # Mock _get_current_usage to return 80 first, then 0
            # to break out of the loop
            usage_values = [80, 0]

            def get_current_usage_side_effect():
                return usage_values.pop(0) if usage_values else 0

            with patch.object(
                limiter, "_get_current_usage", side_effect=get_current_usage_side_effect
            ):
                # Set time such that sleep_time <= 0
                # entry_time + 60.1 - current_time <= 0
                # 1000.0 + 60.1 - current_time <= 0
                # current_time >= 1060.1
                mock_time.return_value = 1060.1  # sleep_time = 0.0

                # Call wait_for_capacity
                await limiter.wait_for_capacity(30)  # 80 + 30 = 110 > 100

                # Should NOT have slept since sleep_time <= 0
                mock_sleep.assert_not_called()

                # _clean_old_usage should have been called
                mock_clean.assert_called()
