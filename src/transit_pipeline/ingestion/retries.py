"""Exponential backoff and timeout handling for live API requests."""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import httpx

from transit_pipeline.domain.exceptions import ApiError

RETRYABLE_STATUS_CODES = frozenset({429, 500, 502, 503, 504})


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    """Retry limits and exponential backoff settings."""

    max_attempts: int = 4
    base_delay: float = 0.5
    max_delay: float = 8.0
    retry_statuses: frozenset[int] = RETRYABLE_STATUS_CODES

    def delay_for(self, attempt: int) -> float:
        """Return the backoff delay before the next attempt (1-based)."""
        return min(self.base_delay * 2.0 ** (attempt - 1), self.max_delay)


def _retry_after_seconds(response: httpx.Response) -> float | None:
    value = response.headers.get("Retry-After")
    if value is None:
        return None
    try:
        return max(0.0, float(value))
    except ValueError:
        return None


def request_with_retries(
    client: httpx.Client,
    url: str,
    *,
    policy: RetryPolicy | None = None,
    sleep: Callable[[float], None] = time.sleep,
    **kwargs: Any,
) -> httpx.Response:
    """Perform a GET request, retrying transient failures with backoff."""
    retry_policy = policy or RetryPolicy()
    last_error: Exception | None = None

    for attempt in range(1, retry_policy.max_attempts + 1):
        try:
            response = client.get(url, **kwargs)
        except httpx.TransportError as exc:
            last_error = exc
            if attempt == retry_policy.max_attempts:
                break
            sleep(retry_policy.delay_for(attempt))
            continue

        if response.status_code in retry_policy.retry_statuses:
            if attempt == retry_policy.max_attempts:
                raise ApiError(
                    f"GET {url} failed with HTTP {response.status_code} "
                    f"after {attempt} attempts"
                )
            sleep(_retry_after_seconds(response) or retry_policy.delay_for(attempt))
            continue

        if response.is_error:
            raise ApiError(f"GET {url} failed with HTTP {response.status_code}")

        return response

    raise ApiError(f"GET {url} failed after {retry_policy.max_attempts} attempts: {last_error}")
