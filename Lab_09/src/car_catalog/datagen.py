"""Deterministic generation of large car catalogs for benchmarks."""

import csv
import random
from pathlib import Path

from car_catalog.models import Car

CATALOG: dict[str, tuple[float, tuple[str, ...]]] = {
    # brand: (base price in USD, models)
    "Toyota": (24000.0, ("Corolla", "Camry", "RAV4", "Yaris", "Prius")),
    "BMW": (46000.0, ("3 Series", "5 Series", "X3", "X5", "i4")),
    "Audi": (44000.0, ("A3", "A4", "A6", "Q5", "Q7")),
    "Skoda": (21000.0, ("Fabia", "Octavia", "Superb", "Kodiaq")),
    "Volkswagen": (27000.0, ("Golf", "Passat", "Tiguan", "Polo")),
    "Ford": (26000.0, ("Focus", "Fiesta", "Mustang", "Kuga")),
    "Honda": (25000.0, ("Civic", "Accord", "CR-V", "Jazz")),
    "Mazda": (23000.0, ("Mazda3", "Mazda6", "CX-5", "MX-5")),
    "Kia": (22000.0, ("Rio", "Ceed", "Sportage", "Sorento")),
    "Hyundai": (22500.0, ("i20", "i30", "Tucson", "Santa Fe")),
    "Renault": (19500.0, ("Clio", "Megane", "Captur", "Duster")),
    "Opel": (20500.0, ("Astra", "Corsa", "Insignia", "Mokka")),
}
BRANDS: tuple[str, ...] = tuple(CATALOG)
FIRST_YEAR = 2000
LAST_YEAR = 2026
CSV_HEADER: tuple[str, ...] = ("brand", "model", "year", "price", "mileage")


def generate_cars(count: int, seed: int = 42) -> list[Car]:
    """Create ``count`` valid cars; the same seed gives the same list."""
    if count < 0:
        raise ValueError("count must not be negative")
    rng = random.Random(seed)
    cars: list[Car] = []
    for _ in range(count):
        brand = rng.choice(BRANDS)
        base_price, models = CATALOG[brand]
        year = rng.randint(FIRST_YEAR, LAST_YEAR)
        age = LAST_YEAR - year
        price = base_price * rng.uniform(0.7, 1.3) * 0.92**age + 500.0
        mileage = int(age * rng.uniform(4000, 22000)) + rng.randint(0, 3000)
        cars.append(
            Car(brand, rng.choice(models), year, round(price, 2), mileage)
        )
    return cars


def write_catalog_csv(cars: list[Car], path: Path) -> Path:
    """Write cars in the format understood by ``import_cars_csv``."""
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(CSV_HEADER)
        for car in cars:
            writer.writerow(
                (car.brand, car.model, car.year, car.price, car.mileage)
            )
    return path


def generate_csv_files(
    directory: Path, files: int, rows_per_file: int, seed: int = 42
) -> list[Path]:
    """Create several catalog files (different data in every file)."""
    if files < 1:
        raise ValueError("files must be positive")
    directory.mkdir(parents=True, exist_ok=True)
    paths = []
    for index in range(files):
        cars = generate_cars(rows_per_file, seed + index)
        paths.append(
            write_catalog_csv(cars, directory / f"catalog_{index:02d}.csv")
        )
    return paths
