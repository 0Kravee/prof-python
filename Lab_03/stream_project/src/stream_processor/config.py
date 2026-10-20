"""Configuration constants of the stream processor."""

MIN_YEAR: int = 1900
MAX_YEAR: int = 2030
MIN_PRICE: float = 0.0
MIN_MILEAGE: int = 0
CURRENCY: str = "USD"
CSV_HEADER: tuple[str, ...] = (
    "id",
    "brand",
    "model",
    "year",
    "price",
    "mileage",
)
