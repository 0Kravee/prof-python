"""Structural interfaces (Protocol) used by the application."""

from collections.abc import Sequence
from typing import Protocol, TypeVar, runtime_checkable

T = TypeVar("T")
T_co = TypeVar("T_co", covariant=True)
T_contra = TypeVar("T_contra", contravariant=True)


class HasId(Protocol):
    """Anything that exposes an integer identifier."""

    @property
    def id(self) -> int: ...


@runtime_checkable
class Notifier(Protocol):
    """Sends a message to the outside world (console, e-mail, ...)."""

    def notify(self, message: str) -> None: ...


class Matcher(Protocol[T_contra]):
    """Decides whether an item satisfies some condition."""

    def matches(self, item: T_contra) -> bool: ...


class ReadableRepository(Protocol[T_co]):
    """Read side of a repository (interface segregation)."""

    def get(self, entity_id: int) -> T_co: ...

    def list_all(self) -> Sequence[T_co]: ...


class WritableRepository(Protocol[T_contra]):
    """Write side of a repository (interface segregation)."""

    def add(self, entity: T_contra) -> None: ...

    def remove(self, entity_id: int) -> None: ...


class Repository(ReadableRepository[T], WritableRepository[T], Protocol[T]):
    """Full repository: both reading and writing."""
