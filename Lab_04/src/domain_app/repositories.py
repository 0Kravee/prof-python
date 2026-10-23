"""Generic in-memory repository."""

from collections.abc import Iterable, Iterator
from typing import Generic, TypeAlias, TypeVar

from domain_app.exceptions import DuplicateEntityError, EntityNotFoundError
from domain_app.models import Vehicle
from domain_app.protocols import HasId, Matcher

# bound TypeVar: the repository can store only entities that have an id
E = TypeVar("E", bound=HasId)


class InMemoryRepository(Generic[E]):
    """Parameterised repository: ``InMemoryRepository[Vehicle]``."""

    def __init__(self, entities: Iterable[E] = ()) -> None:
        self._items: dict[int, E] = {}
        for entity in entities:
            self.add(entity)

    def add(self, entity: E) -> None:
        if entity.id in self._items:
            raise DuplicateEntityError(f"Entity {entity.id} already exists")
        self._items[entity.id] = entity

    def get(self, entity_id: int) -> E:
        try:
            return self._items[entity_id]
        except KeyError:
            raise EntityNotFoundError(
                f"Entity {entity_id} was not found"
            ) from None

    def remove(self, entity_id: int) -> None:
        self.get(entity_id)
        del self._items[entity_id]

    def list_all(self) -> list[E]:
        return list(self._items.values())

    def find(self, matcher: Matcher[E]) -> list[E]:
        return [e for e in self._items.values() if matcher.matches(e)]

    def __len__(self) -> int:
        return len(self._items)

    def __iter__(self) -> Iterator[E]:
        return iter(self._items.values())

    def __contains__(self, entity_id: object) -> bool:
        return entity_id in self._items


VehicleRepository: TypeAlias = InMemoryRepository[Vehicle]
