"""Application entry point for the car catalog laboratory project."""

from car_catalog.models import Car
from car_catalog.services import (
    calculate_average_price,
    filter_by_year,
    find_lowest_mileage,
    find_most_expensive,
    search_by_brand,
    sort_by_price,
)


def create_demo_cars() -> list[Car]:
    """Create a small demo dataset of cars."""
    return [
        Car(brand="Toyota", model="Camry", year=2019, price=21500.0, mileage=45000),
        Car(brand="BMW", model="X5", year=2021, price=48200.0, mileage=18000),
        Car(brand="Toyota", model="Corolla", year=2022, price=19800.0, mileage=9000),
        Car(brand="Audi", model="A4", year=2018, price=23000.0, mileage=62000),
        Car(brand="BMW", model="3 Series", year=2020, price=31000.0, mileage=27000),
    ]


def print_cars(cars: list[Car]) -> None:
    """Print a formatted table of cars."""
    print(f"{'Car':<25}{'Year':<8}{'Price':<12}{'Mileage':<10}")
    print("-" * 55)
    for car in cars:
        print(
            f"{car.full_name:<25}"
            f"{car.year:<8}"
            f"{car.price:<12.2f}"
            f"{car.mileage:<10}"
        )


def print_menu() -> None:
    print()
    print("1. Show all cars")
    print("2. Search by brand")
    print("3. Filter by year")
    print("4. Show most expensive car")
    print("5. Show average price")
    print("6. Show car with lowest mileage")
    print("7. Show cars sorted by price")
    print("8. Exit")


def run_menu(cars: list[Car]) -> None:
    """Run an interactive console menu on top of the car catalog."""
    while True:
        print_menu()
        command = input("Select command: ").strip()
        if command == "1":
            print_cars(cars)
        elif command == "2":
            brand = input("Brand: ").strip()
            print_cars(search_by_brand(cars, brand))
        elif command == "3":
            year_input = input("Year: ").strip()
            if not year_input.isdigit():
                print("Year must be a number.")
                continue
            print_cars(filter_by_year(cars, int(year_input)))
        elif command == "4":
            best = find_most_expensive(cars)
            if best is not None:
                print(f"\nMost expensive car: {best.full_name} ({best.price:.2f})")
        elif command == "5":
            average = calculate_average_price(cars)
            print(f"\nAverage price: {average:.2f}")
        elif command == "6":
            lowest = find_lowest_mileage(cars)
            if lowest is not None:
                print(f"\nLowest mileage: {lowest.full_name} ({lowest.mileage} km)")
        elif command == "7":
            print_cars(sort_by_price(cars))
        elif command == "8":
            print("Goodbye.")
            break
        else:
            print("Unknown command.")


def main() -> None:
    cars = create_demo_cars()

    print("ALL CARS")
    print_cars(cars)

    brand = "Toyota"
    print(f"\nCARS OF BRAND {brand}")
    print_cars(search_by_brand(cars, brand))

    year = 2019
    print(f"\nCARS OF YEAR {year}")
    print_cars(filter_by_year(cars, year))

    average = calculate_average_price(cars)
    print(f"\nAverage price: {average:.2f}")

    most_expensive = find_most_expensive(cars)
    if most_expensive is not None:
        print(f"Most expensive car: {most_expensive.full_name} ({most_expensive.price:.2f})")

    lowest_mileage = find_lowest_mileage(cars)
    if lowest_mileage is not None:
        print(f"Lowest mileage car: {lowest_mileage.full_name} ({lowest_mileage.mileage} km)")

    print("\nCARS SORTED BY PRICE")
    print_cars(sort_by_price(cars))


if __name__ == "__main__":
    main()
