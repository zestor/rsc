from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import TypeVar

T = TypeVar("T")


@dataclass(frozen=True)
class RetryPolicy:
    max_retries: int = 5
    base_delay_seconds: float = 5.0

    def delay_for_retry(self, retry_number: int) -> float:
        return self.base_delay_seconds * retry_number


DEFAULT_RETRY_POLICY = RetryPolicy()


RETRYABLE_ERROR_NAMES = (
    "APIConnectionError",
    "APIError",
    "APITimeoutError",
    "ConnectionError",
    "ConnectTimeout",
    "HTTPError",
    "InternalServerError",
    "RateLimitError",
    "ReadTimeout",
    "RemoteDisconnected",
    "ServiceUnavailableError",
    "TimeoutError",
)

NON_RETRYABLE_ERROR_NAMES = (
    "AuthenticationError",
    "BadRequestError",
    "ConflictError",
    "ContentFilterError",
    "ForbiddenError",
    "NotFoundError",
    "NotFoundResponseError",
    "PermissionDeniedError",
    "UnprocessableEntityError",
    "ValidationError",
)


def is_retryable_exception(exc: BaseException) -> bool:
    if isinstance(exc, OSError):
        return True
    name = exc.__class__.__name__
    if any(non_retryable in name for non_retryable in NON_RETRYABLE_ERROR_NAMES):
        return False
    return any(retryable in name for retryable in RETRYABLE_ERROR_NAMES)


def retry_call(
    operation: Callable[[], T],
    *,
    policy: RetryPolicy = DEFAULT_RETRY_POLICY,
    is_retryable: Callable[[BaseException], bool] = is_retryable_exception,
    on_retry: Callable[[BaseException, int, float], None] | None = None,
    sleep: Callable[[float], None] | None = None,
) -> T:
    retry_number = 0
    while True:
        try:
            return operation()
        except Exception as exc:
            if retry_number >= policy.max_retries or not is_retryable(exc):
                raise
            retry_number += 1
            delay = policy.delay_for_retry(retry_number)
            if on_retry is not None:
                on_retry(exc, retry_number, delay)
            (sleep or time.sleep)(delay)
