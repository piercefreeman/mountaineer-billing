import asyncio
from inspect import iscoroutinefunction
from random import uniform
from time import sleep
from typing import Type


def backoff_fn(
    *,
    max_tries: int,
    exceptions: tuple[Type[Exception], ...] = (Exception,),
    start_sleep_time: float = 1.0,
    factor: int = 2,
    max_jitter: float = 0.5,
):
    """
    Simple exponential backoff implementation with jitter.

    """

    def decorator(func):
        if iscoroutinefunction(func):

            async def wrapper(*args, **kwargs):  # type: ignore
                attempts = 0
                sleep_time = start_sleep_time
                while attempts < max_tries:
                    try:
                        return await func(*args, **kwargs)
                    except exceptions:
                        attempts += 1
                        if attempts == max_tries:
                            raise
                        jitter = uniform(0, max_jitter)
                        await asyncio.sleep(sleep_time + jitter)
                        sleep_time *= factor
        else:

            def wrapper(*args, **kwargs):
                attempts = 0
                sleep_time = start_sleep_time
                while attempts < max_tries:
                    try:
                        return func(*args, **kwargs)
                    except exceptions:
                        attempts += 1
                        if attempts == max_tries:
                            raise
                        jitter = uniform(0, max_jitter)
                        sleep(sleep_time + jitter)
                        sleep_time *= factor

        return wrapper

    return decorator
