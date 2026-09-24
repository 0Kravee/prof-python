"""Decorators used across the car catalog laboratory project."""

from collections import deque
from functools import wraps
from time import perf_counter


def measure_time(func):
    """Decorator that prints how long the wrapped function took to run."""

    @wraps(func)
    def wrapper(*args, **kwargs):
        start = perf_counter()
        result = func(*args, **kwargs)
        elapsed = perf_counter() - start
        print(f"{func.__name__}: {elapsed:.8f} s")
        return result

    return wrapper


def track_history(history: deque):
    """Parameterized decorator factory (closure over `history`).

    Every call of the decorated function appends its name to the given
    deque, which keeps only the last `history.maxlen` operations - this is
    a convenient use case for `collections.deque`.
    """

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            result = func(*args, **kwargs)
            history.append(func.__name__)
            return result

        return wrapper

    return decorator
