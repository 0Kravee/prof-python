"""Search criteria abstraction (strategy pattern)."""

from abc import ABC, abstractmethod

from domain_app.models import Vehicle


class SearchCriteria(ABC):
    """Abstract search criterion; concrete criteria are interchangeable.

    Criteria can be combined with ``&`` (and), ``|`` (or) and ``~`` (not).
    """

    @abstractmethod
    def matches(self, item: Vehicle) -> bool:
        """Return True if the vehicle satisfies the criterion."""

    def __call__(self, item: Vehicle) -> bool:
        return self.matches(item)

    def __and__(self, other: "SearchCriteria") -> "SearchCriteria":
        return AndCriteria(self, other)

    def __or__(self, other: "SearchCriteria") -> "SearchCriteria":
        return OrCriteria(self, other)

    def __invert__(self) -> "SearchCriteria":
        return NotCriteria(self)


class BrandCriteria(SearchCriteria):
    def __init__(self, brand: str) -> None:
        self._brand = brand.strip().lower()

    def matches(self, item: Vehicle) -> bool:
        return item.brand.lower() == self._brand


class ModelCriteria(SearchCriteria):
    def __init__(self, model: str) -> None:
        self._model = model.strip().lower()

    def matches(self, item: Vehicle) -> bool:
        return item.model.lower() == self._model


class BrandOrModelCriteria(SearchCriteria):
    """Free-text search: the query is a part of the brand or model."""

    def __init__(self, query: str) -> None:
        self._query = query.strip().lower()

    def matches(self, item: Vehicle) -> bool:
        return self._query in item.brand.lower() or (
            self._query in item.model.lower()
        )


class YearCriteria(SearchCriteria):
    """Exact production year."""

    def __init__(self, year: int) -> None:
        self._year = year

    def matches(self, item: Vehicle) -> bool:
        return item.year == self._year


class YearRangeCriteria(SearchCriteria):
    """Production year within [min_year, max_year]."""

    def __init__(
        self, min_year: int | None = None, max_year: int | None = None
    ) -> None:
        self._min_year = min_year
        self._max_year = max_year

    def matches(self, item: Vehicle) -> bool:
        if self._min_year is not None and item.year < self._min_year:
            return False
        return self._max_year is None or item.year <= self._max_year


class AndCriteria(SearchCriteria):
    def __init__(self, left: SearchCriteria, right: SearchCriteria) -> None:
        self._left = left
        self._right = right

    def matches(self, item: Vehicle) -> bool:
        return self._left.matches(item) and self._right.matches(item)


class OrCriteria(SearchCriteria):
    def __init__(self, left: SearchCriteria, right: SearchCriteria) -> None:
        self._left = left
        self._right = right

    def matches(self, item: Vehicle) -> bool:
        return self._left.matches(item) or self._right.matches(item)


class NotCriteria(SearchCriteria):
    def __init__(self, inner: SearchCriteria) -> None:
        self._inner = inner

    def matches(self, item: Vehicle) -> bool:
        return not self._inner.matches(item)
