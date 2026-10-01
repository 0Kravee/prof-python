"""Structured input data for the car catalog laboratory project (variant 5)."""

# tuple: an immutable, ordered structure - used here to fix the set of fields
# that every car record must contain.
CAR_FIELDS: tuple[str, ...] = ("id", "brand", "model", "year", "price", "mileage")

# list of dict: the primary structure holding the whole dataset. list is used
# because the collection is ordered and its size may change (new cars can be
# appended), while each car is a dict, since data is naturally represented as
# key -> value pairs.
cars: list[dict] = [
    {"id": 1, "brand": "Toyota", "model": "Camry", "year": 2019, "price": 21500.0, "mileage": 45000},
    {"id": 2, "brand": "BMW", "model": "X5", "year": 2021, "price": 48200.0, "mileage": 18000},
    {"id": 3, "brand": "Toyota", "model": "Corolla", "year": 2022, "price": 19800.0, "mileage": 9000},
    {"id": 4, "brand": "Audi", "model": "A4", "year": 2018, "price": 23000.0, "mileage": 62000},
    {"id": 5, "brand": "BMW", "model": "3 Series", "year": 2020, "price": 31000.0, "mileage": 27000},
    {"id": 6, "brand": "Audi", "model": "Q7", "year": 2021, "price": 54500.0, "mileage": 21000},
    {"id": 7, "brand": "Toyota", "model": "RAV4", "year": 2020, "price": 27300.0, "mileage": 33000},
]
