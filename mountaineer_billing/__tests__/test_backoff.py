from typing import Type

import pytest

from mountaineer_billing.backoff import backoff_fn


class CustomTestError(Exception):
    """
    Custom exception class for testing.
    """


class AnotherError(Exception):
    """
    Another custom exception class for testing.
    """


@pytest.mark.parametrize(
    "raised_exception, handled_exceptions, expected_attempts",
    [
        (CustomTestError, [CustomTestError], 3),
        (CustomTestError, [AnotherError], 1),
        (AnotherError, [CustomTestError, AnotherError], 3),
    ],
)
@pytest.mark.asyncio
async def test_backoff(
    raised_exception: Type[Exception],
    handled_exceptions: list[Type[Exception]],
    expected_attempts: int,
):
    sync_attempts = 0
    async_attempts = 0

    @backoff_fn(
        exceptions=tuple(handled_exceptions),
        max_tries=3,
        start_sleep_time=0.1,
        factor=2,
        max_jitter=0.05,
    )
    def sync_func():
        nonlocal sync_attempts
        sync_attempts += 1
        raise raised_exception("Failure")

    @backoff_fn(
        exceptions=tuple(handled_exceptions),
        max_tries=3,
        start_sleep_time=0.1,
        factor=2,
        max_jitter=0.05,
    )
    async def async_func():
        nonlocal async_attempts
        async_attempts += 1
        raise raised_exception("Failure")

    with pytest.raises(raised_exception):
        sync_func()
    assert sync_attempts == expected_attempts

    with pytest.raises(raised_exception):
        await async_func()
    assert async_attempts == expected_attempts
