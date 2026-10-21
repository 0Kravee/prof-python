"""Record type passed between pipeline stages."""

from typing import NamedTuple


class CarRecord(NamedTuple):
    """One validated row of the car catalog."""

    car_id: int
    brand: str
    model: str
    year: int
    price: float
    mileage: int
