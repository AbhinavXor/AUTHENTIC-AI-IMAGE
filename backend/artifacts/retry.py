from __future__ import annotations

import asyncio
import random
from collections.abc import Awaitable, Callable
from typing import TypeVar

from ai.provider_adapter import ProviderError

T = TypeVar("T")

_RETRYABLE_PROVIDER_CODES = {
    "availability",
    "connection",
    "rate_limit",
    "timeout",
    "unknown",
}


async def run_with_provider_retry(
    operation: Callable[[], Awaitable[T]],
    *,
    maximum_attempts: int = 3,
    base_delay_seconds: float = 0.45,
    maximum_delay_seconds: float = 3.0,
) -> T:
    """Run a provider operation with bounded retry and jitter.

    Authentication, billing, configuration, request, and response-contract
    failures are intentionally not retried because they are not transient.
    """

    if maximum_attempts < 1:
        raise ValueError("maximum_attempts must be positive.")

    random_source = random.SystemRandom()

    for attempt in range(1, maximum_attempts + 1):
        try:
            return await operation()
        except ProviderError as error:
            should_retry = (
                attempt < maximum_attempts
                and error.retryable
                and error.code in _RETRYABLE_PROVIDER_CODES
            )
            if not should_retry:
                raise

            exponential_delay = min(
                maximum_delay_seconds,
                base_delay_seconds * (2 ** (attempt - 1)),
            )
            jitter = random_source.uniform(0.0, exponential_delay * 0.25)
            await asyncio.sleep(exponential_delay + jitter)

    raise RuntimeError("Provider retry loop terminated unexpectedly.")
