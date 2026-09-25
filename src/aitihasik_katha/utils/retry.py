import time
from functools import wraps
from typing import Callable, ParamSpec, TypeVar

from ..core.logging import get_logger


logger = get_logger(__name__)

P = ParamSpec("P")
T = TypeVar("T")


def retry(
    exceptions: tuple[type[BaseException], ...],
    max_attempts: int = 3,
    delay_seconds: float = 5.0,
    backoff_keywords: tuple[str, ...] = (),
    backoff_delay_seconds: float = 30.0,
) -> Callable[[Callable[P, T]], Callable[P, T]]:
    """Retry a function on the given exceptions, with a longer wait when the
    error message matches one of ``backoff_keywords`` (e.g. quota/rate limits)."""

    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        @wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            attempt = 0
            while True:
                try:
                    return func(*args, **kwargs)
                except exceptions as exc:
                    attempt += 1
                    if attempt >= max_attempts:
                        raise
                    message = str(exc).lower()
                    if backoff_keywords and any(keyword in message for keyword in backoff_keywords):
                        wait_seconds = backoff_delay_seconds
                    else:
                        wait_seconds = delay_seconds
                    logger.warning(
                        "%s failed (attempt %s/%s): %s. Retrying in %ss",
                        func.__name__, attempt, max_attempts, exc, wait_seconds,
                    )
                    time.sleep(wait_seconds)

        return wrapper

    return decorator
