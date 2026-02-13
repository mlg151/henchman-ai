"""Tests for retry utilities."""

import pytest

from henchman.utils.retry import (
    RetryConfig,
    calculate_delay,
    retry_async,
    with_retry,
)


class TestRetryConfig:
    """Tests for RetryConfig dataclass."""

    def test_default_config(self) -> None:
        """Default config has sensible values."""
        config = RetryConfig()
        assert config.max_retries == 3
        assert config.base_delay == 1.0
        assert config.max_delay == 30.0
        assert config.exponential_base == 2.0
        assert config.jitter is True
        assert ConnectionError in config.retryable_exceptions

    def test_custom_config(self) -> None:
        """Can create custom config."""
        config = RetryConfig(
            max_retries=5,
            base_delay=0.5,
            max_delay=60.0,
            exponential_base=3.0,
            jitter=False,
        )
        assert config.max_retries == 5
        assert config.base_delay == 0.5
        assert config.max_delay == 60.0
        assert config.exponential_base == 3.0
        assert config.jitter is False


class TestCalculateDelay:
    """Tests for calculate_delay function."""

    def test_first_attempt(self) -> None:
        """First attempt uses base delay."""
        config = RetryConfig(base_delay=1.0, jitter=False)
        delay = calculate_delay(0, config)
        assert delay == 1.0

    def test_exponential_growth(self) -> None:
        """Delay grows exponentially."""
        config = RetryConfig(base_delay=1.0, exponential_base=2.0, jitter=False)
        assert calculate_delay(0, config) == 1.0
        assert calculate_delay(1, config) == 2.0
        assert calculate_delay(2, config) == 4.0
        assert calculate_delay(3, config) == 8.0

    def test_max_delay_cap(self) -> None:
        """Delay is capped at max_delay."""
        config = RetryConfig(
            base_delay=1.0,
            max_delay=5.0,
            exponential_base=2.0,
            jitter=False,
        )
        # 2^10 = 1024, but should be capped at 5
        delay = calculate_delay(10, config)
        assert delay == 5.0

    def test_jitter_adds_variability(self) -> None:
        """Jitter adds random variability."""
        config = RetryConfig(base_delay=1.0, jitter=True)
        # With jitter, delay should be between base and base * 1.5
        delays = [calculate_delay(0, config) for _ in range(100)]
        assert all(1.0 <= d <= 1.5 for d in delays)
        # Should have some variability
        assert len(set(delays)) > 1


class TestWithRetryDecorator:
    """Tests for with_retry decorator."""

    async def test_success_on_first_try(self) -> None:
        """Function succeeds without retries."""
        call_count = 0

        @with_retry(RetryConfig(max_retries=3))
        async def succeed() -> str:
            nonlocal call_count
            call_count += 1
            return "success"

        result = await succeed()
        assert result == "success"
        assert call_count == 1

    async def test_success_after_retry(self) -> None:
        """Function succeeds after transient failures."""
        call_count = 0

        @with_retry(RetryConfig(max_retries=3, base_delay=0.01))
        async def fail_then_succeed() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("Transient failure")
            return "success"

        result = await fail_then_succeed()
        assert result == "success"
        assert call_count == 3

    async def test_exhaust_retries(self) -> None:
        """Exception raised after all retries exhausted."""
        call_count = 0

        @with_retry(RetryConfig(max_retries=2, base_delay=0.01))
        async def always_fail() -> str:
            nonlocal call_count
            call_count += 1
            raise ConnectionError("Permanent failure")

        with pytest.raises(ConnectionError, match="Permanent failure"):
            await always_fail()
        assert call_count == 3  # Initial + 2 retries

    async def test_non_retryable_exception(self) -> None:
        """Non-retryable exceptions are raised immediately."""
        call_count = 0

        @with_retry(RetryConfig(max_retries=3))
        async def raise_value_error() -> str:
            nonlocal call_count
            call_count += 1
            raise ValueError("Not retryable")

        with pytest.raises(ValueError, match="Not retryable"):
            await raise_value_error()
        assert call_count == 1  # No retries

    async def test_default_config(self) -> None:
        """Decorator works with default config."""

        @with_retry()
        async def succeed() -> str:
            return "ok"

        result = await succeed()
        assert result == "ok"

    async def test_custom_retryable_exceptions(self) -> None:
        """Can specify custom retryable exceptions."""
        call_count = 0

        @with_retry(
            RetryConfig(
                max_retries=2,
                base_delay=0.01,
                retryable_exceptions=(ValueError,),
            )
        )
        async def fail_with_value_error() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("Retryable now")
            return "success"

        result = await fail_with_value_error()
        assert result == "success"
        assert call_count == 3


class TestRetryAsync:
    """Tests for retry_async function."""

    async def test_success(self) -> None:
        """Functional retry succeeds."""

        async def succeed() -> str:
            return "ok"

        result = await retry_async(succeed)
        assert result == "ok"

    async def test_retry_on_failure(self) -> None:
        """Functional retry retries on failure."""
        call_count = 0

        async def fail_once() -> str:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ConnectionError("Transient")
            return "recovered"

        result = await retry_async(
            fail_once,
            config=RetryConfig(max_retries=2, base_delay=0.01),
        )
        assert result == "recovered"
        assert call_count == 2

    async def test_default_config(self) -> None:
        """Works with default config."""

        async def succeed() -> str:
            return "default"

        result = await retry_async(succeed)
        assert result == "default"

    async def test_all_retries_fail(self) -> None:
        """Raises last exception after all retries fail."""

        async def always_fail() -> str:
            raise TimeoutError("Always times out")

        with pytest.raises(TimeoutError, match="Always times out"):
            await retry_async(
                always_fail,
                config=RetryConfig(max_retries=1, base_delay=0.01),
            )
