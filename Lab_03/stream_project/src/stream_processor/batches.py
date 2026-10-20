"""Batch processing helpers."""

from collections.abc import Callable, Iterable, Iterator
from itertools import islice
from typing import TypeVar

from stream_processor.exceptions import InvalidBatchSizeError

T = TypeVar("T")


def batched(iterable: Iterable[T], size: int) -> Iterator[list[T]]:
    """Yield lists of at most `size` items; only one batch is in memory."""
    if size <= 0:
        raise InvalidBatchSizeError("Batch size must be positive")
    iterator = iter(iterable)
    while True:
        batch = list(islice(iterator, size))
        if not batch:
            return
        yield batch


def dynamic_batches(
    iterable: Iterable[T],
    max_weight: float,
    weight: Callable[[T], float],
) -> Iterator[list[T]]:
    """Dynamic batching: close a batch when the weight limit is exceeded."""
    batch: list[T] = []
    total = 0.0
    for item in iterable:
        item_weight = weight(item)
        if batch and total + item_weight > max_weight:
            yield batch
            batch, total = [], 0.0
        batch.append(item)
        total += item_weight
    if batch:
        yield batch


batched_cars = batched
