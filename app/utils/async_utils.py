"""
Async Utilities Module

Provides utilities for safely running async coroutines in various contexts,
particularly for RunPod serverless environments where async handler support
has known issues.
"""
import asyncio
import concurrent.futures
from typing import TypeVar, Coroutine, Any


T = TypeVar('T')


def run_async(coro: Coroutine[Any, Any, T]) -> T:
    """
    Run an async coroutine safely, handling existing event loops.

    This function is necessary because RunPod's async handler support has known
    issues (GitHub #387 - coroutines not being awaited properly). Instead of
    using RunPod's async handler, we use a sync handler and manually manage
    the event loop ourselves.

    The function handles three scenarios:
    1. Event loop exists and is running: Creates a new loop in a separate thread
       using ThreadPoolExecutor to avoid conflicts with the running loop.
    2. Event loop exists but is not running: Uses the existing loop directly
       with run_until_complete.
    3. No event loop exists: Creates a new loop using asyncio.run.

    Args:
        coro: The async coroutine to execute.

    Returns:
        The result of the coroutine execution.

    Raises:
        Any exception raised by the coroutine will be propagated to the caller.

    Example:
        >>> async def fetch_data(url: str) -> dict:
        ...     return {"data": "example"}
        >>> result = run_async(fetch_data("https://example.com"))
    """
    try:
        loop = asyncio.get_event_loop()

        if loop.is_running():
            # We're in an async context - create new loop in thread
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, coro)
                return future.result()
        else:
            # No running loop - use it directly
            return loop.run_until_complete(coro)

    except RuntimeError:
        # No event loop exists - create one
        return asyncio.run(coro)
