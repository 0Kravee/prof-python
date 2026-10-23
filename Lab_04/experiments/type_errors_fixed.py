"""The same module after the three type errors were fixed.

Run:  python -m mypy experiments/type_errors_fixed.py
"""

from domain_app.models import Car
from domain_app.repositories import InMemoryRepository

# Fix 1: the value has the declared type
production_year: int = 2020


# Fix 2: the function returns what it promises
def total_price() -> int:
    return 100


# Fix 3: the repository of Car receives a Car
repository: InMemoryRepository[Car] = InMemoryRepository()
repository.add(Car("Audi", "A4", 2018, 23000, 62000))
