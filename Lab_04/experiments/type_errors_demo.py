"""Type-checking experiment: three deliberate type errors.

Run:  python -m mypy experiments/type_errors_demo.py
"""

from domain_app.models import Car
from domain_app.repositories import InMemoryRepository
from domain_app.value_objects import VehicleSpecification

# Error 1: a str is assigned to a variable declared as int
production_year: int = "2020"


# Error 2: the function promises int, but returns str
def total_price() -> int:
    return "100"


# Error 3: a repository of Car receives a VehicleSpecification
repository: InMemoryRepository[Car] = InMemoryRepository()
repository.add(VehicleSpecification("Audi", "A4", 2018))
