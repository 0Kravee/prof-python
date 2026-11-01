"""Application entry point for the car catalog laboratory project."""

import sys
from pathlib import Path

# Allows running this file directly (``python main.py``) without
# installing the package: the ``src`` directory is added to sys.path.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from car_catalog.config import CURRENCY  # noqa: E402
from car_catalog.exceptions import CarCatalogError  # noqa: E402
from car_catalog.models import Car  # noqa: E402
from car_catalog.services import (  # noqa: E402
    add_car,
    calculate_average_price,
    filter_by_year,
    find_lowest_mileage,
    find_most_expensive,
    get_statistics,
    search_by_brand,
    search_cars,
    sort_by_price,
)


def create_demo_cars() -> list[Car]:
    """Create a small demo dataset of cars."""
    return [
        Car("Toyota", "Camry", 2019, 21500.0, 45000),
        Car("BMW", "X5", 2021, 48200.0, 18000),
        Car("Toyota", "Corolla", 2022, 19800.0, 9000),
        Car("Audi", "A4", 2018, 23000.0, 62000),
        Car("BMW", "3 Series", 2020, 31000.0, 27000),
    ]


def print_cars(cars: list[Car]) -> None:
    """Print a formatted table of cars."""
    print(f"{'Car':<22}{'Year':<7}{'Price':<12}{'Mileage':<10}")
    print("-" * 51)
    if not cars:
        print("(no cars)")
    for car in cars:
        print(
            f"{car.full_name:<22}{car.year:<7}"
            f"{car.price:<12.2f}{car.mileage:<10}"
        )


def run_demo(cars: list[Car]) -> None:
    """Non-interactive demonstration of all catalog operations."""
    print("ALL CARS")
    print_cars(cars)

    brand = "Toyota"
    print(f"\nCARS OF BRAND {brand}")
    print_cars(search_by_brand(cars, brand))

    year = 2019
    print(f"\nCARS OF YEAR {year}")
    print_cars(filter_by_year(cars, year))

    average = calculate_average_price(cars)
    print(f"\nAverage price: {average:.2f} {CURRENCY}")

    expensive = find_most_expensive(cars)
    if expensive is not None:
        print(f"Most expensive car: {expensive}")

    lowest = find_lowest_mileage(cars)
    if lowest is not None:
        print(f"Lowest mileage car: {lowest}")

    print("\nCARS SORTED BY PRICE")
    print_cars(sort_by_price(cars))

    print("\nSEARCH: BMW, year >= 2020, price <= 40000")
    print_cars(search_cars(cars, "BMW", min_year=2020, max_price=40000))

    stats = get_statistics(cars)
    print("\nSTATISTICS")
    print(f"Cars: {int(stats['count'])}")
    print(f"Average price: {stats['average_price']:.2f} {CURRENCY}")
    print(
        f"Min / max price: {stats['min_price']:.2f} / {stats['max_price']:.2f}"
    )
    print(f"Average mileage: {stats['average_mileage']:.0f} km")


def read_line(prompt: str) -> str | None:
    """Read a line; return None when input is closed or interrupted."""
    try:
        return input(prompt).strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return None


def read_number(prompt: str, cast: type) -> float | int | None:
    """Read and validate a number; None on invalid input or end of input."""
    raw = read_line(prompt)
    if raw is None:
        return None
    try:
        return cast(raw)  # type: ignore[no-any-return]
    except ValueError:
        print(f"Invalid value: {raw!r}")
        return None


def read_new_car() -> Car | None:
    """Read car data from the keyboard and build a validated Car."""
    brand = read_line("Brand: ")
    model = read_line("Model: ")
    if brand is None or model is None:
        return None
    year = read_number("Year: ", int)
    price = read_number("Price: ", float)
    mileage = read_number("Mileage: ", int)
    if year is None or price is None or mileage is None:
        return None
    return Car(brand, model, int(year), float(price), int(mileage))


MENU = (
    "\n1. Show all cars\n2. Search by brand\n3. Filter by year\n"
    "4. Most expensive car\n5. Average price\n6. Lowest mileage car\n"
    "7. Sort by price\n8. Multi-criteria search\n9. Statistics\n"
    "10. Add a car\n0. Exit"
)


def run_menu(cars: list[Car]) -> None:
    """Interactive menu (only used in a real terminal)."""
    while True:
        print(MENU)
        command = read_line("Select command: ")
        if command is None or command == "0":
            print("Goodbye.")
            return
        try:
            handle_command(command, cars)
        except CarCatalogError as error:
            print(f"Error: {error}")


def handle_command(command: str, cars: list[Car]) -> None:
    """Execute one menu command."""
    if command == "1":
        print_cars(cars)
    elif command == "2":
        brand = read_line("Brand: ")
        if brand is not None:
            print_cars(search_by_brand(cars, brand))
    elif command == "3":
        year = read_number("Year: ", int)
        if year is not None:
            print_cars(filter_by_year(cars, int(year)))
    elif command == "4":
        print(find_most_expensive(cars) or "(no cars)")
    elif command == "5":
        print(f"Average price: {calculate_average_price(cars):.2f}")
    elif command == "6":
        print(find_lowest_mileage(cars) or "(no cars)")
    elif command == "7":
        print_cars(sort_by_price(cars))
    elif command == "8":
        brand = read_line("Brand (empty = any): ")
        year = read_number("Min year: ", int)
        price = read_number("Max price: ", float)
        print_cars(
            search_cars(
                cars,
                brand or None,
                None if year is None else int(year),
                None if price is None else float(price),
            )
        )
    elif command == "9":
        for key, value in get_statistics(cars).items():
            print(f"{key}: {value:.2f}")
    elif command == "10":
        car = read_new_car()
        if car is not None:
            add_car(cars, car)
            print(f"Added: {car}")
    else:
        print("Unknown command.")


def main() -> None:
    cars = create_demo_cars()
    run_demo(cars)
    # The interactive menu starts only in a real terminal, so automated
    # (headless) runs never block or fail on input().
    if sys.stdin is not None and sys.stdin.isatty():
        run_menu(cars)


if __name__ == "__main__":
    main()
