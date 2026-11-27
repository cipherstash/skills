"""A decorator that keeps the signature of the function it wraps."""

import functools
import logging
from collections.abc import Callable

logger = logging.getLogger(__name__)


def logged[**P, R](func: Callable[P, R]) -> Callable[P, R]:
    """Log each call to func at debug level."""

    @functools.wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        logger.debug("calling %s", func.__name__)
        return func(*args, **kwargs)

    return wrapper
