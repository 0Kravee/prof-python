"""Application entry point for the car catalog data-processing project."""

from collections import deque
from time import perf_counter

from data_processor.analytics import (
    calculate_average_price,
    calculate_average_values,
    create_car_record,
    create_year_filter,
    find_linear,
    find_lowest_mileage,
    find_most_expensive,
    sort_by_price,
    sort_items,
)
from data_processor.data import cars
from data_processor.decorators import track_history
from data_processor.processors import (
    count_cars_by_brand,
    create_car_index,
    filter_by_year,
    filter_items,
    get_unique_brand_model_pairs,
    get_unique_brands,
    group_by_brand,
    group_by_brand_and_year,
)

# deque with a fixed size: keeps only the last 10 executed operations
call_history: deque = deque(maxlen=10)


@track_history(call_history)
def show_all_cars(items: list[dict]) -> None:
    print_cars("All cars", items)


@track_history(call_history)
def show_year_filter(items: list[dict], year: int) -> None:
    print_cars(f"Cars manufactured in {year}", filter_by_year(items, year))


def print_cars(title: str, items: list[dict]) -> None:
    print(f"\n{title}")
    print("-" * 65)
    for car in items:
        print(
            f"{car['id']:3} "
            f"{car['brand']:8} "
            f"{car['model']:12} "
            f"{car['year']:6} "
            f"{car['price']:10.2f} "
            f"{car['mileage']:8}"
        )


def run_benchmark(sizes: tuple[int, ...] = (1_000, 10_000, 100_000)) -> list[dict]:
    """Compare linear search in a list with dict-index search for various sizes."""
    results = []
    for size in sizes:
        large_cars = [
            create_car_record(
                id=i,
                brand="Brand",
                model="Model",
                year=2000 + (i % 20),
                price=float(1000 + i),
                mileage=i,
            )
            for i in range(size)
        ]
        index = create_car_index(large_cars)
        target_id = size - 1

        start = perf_counter()
        find_linear(large_cars, target_id)
        linear_time = perf_counter() - start

        start = perf_counter()
        index.get(target_id)
        dict_time = perf_counter() - start

        results.append({"size": size, "linear_seconds": linear_time, "dict_seconds": dict_time})
    return results


def main() -> None:
    show_all_cars(cars)

    brands = get_unique_brands(cars)
    print("\nUnique brands:", brands)

    brand_model_pairs = get_unique_brand_model_pairs(cars)
    print("Unique (brand, model) pairs:", brand_model_pairs)

    average_price = calculate_average_price(cars)
    print(f"\nAverage price: {average_price:.2f}")

    most_expensive = find_most_expensive(cars)
    if most_expensive:
        print("Most expensive car:", most_expensive["brand"], most_expensive["model"], most_expensive["price"])

    lowest_mileage = find_lowest_mileage(cars)
    if lowest_mileage:
        print("Lowest mileage car:", lowest_mileage["brand"], lowest_mileage["model"], lowest_mileage["mileage"])

    ranking = sort_by_price(cars)
    print_cars("Cars ranked by price", ranking)

    brand_counter = count_cars_by_brand(cars)
    print("\nCars by brand:")
    for brand, count in brand_counter.items():
        print(brand, count)

    grouped = group_by_brand(cars)
    print("\nGrouped by brand:")
    for brand, members in grouped.items():
        print(brand, "->", len(members))

    nested = group_by_brand_and_year(cars)
    print("\nGrouped by brand and year:")
    for brand, years in nested.items():
        for year, members in years.items():
            print(brand, year, "->", len(members))

    index = create_car_index(cars)
    car_id = 3
    print("\nSearch by ID:", index.get(car_id))

    is_recent = create_year_filter(2020)
    recent_cars = filter_items(cars, is_recent)
    print_cars("Cars from 2020 or newer", recent_cars)

    show_year_filter(cars, 2019)

    cheap_first = sort_items(cars, key=lambda car: car["price"], reverse=False)
    print_cars("Cars ranked by price (ascending, universal sort)", cheap_first)

    demo_average = calculate_average_values(21500, 48200, 19800, 23000)
    print("\nAverage via *args:", demo_average)

    new_car = create_car_record(id=8, brand="Skoda", model="Octavia", year=2023, price=26500.0, mileage=1200)
    print("Created via **kwargs:", new_car)

    print("\nCall history (deque):", list(call_history))

    print("\nBENCHMARK: linear search vs dict index search")
    print("-" * 65)
    print(f"{'Size':>10} {'Linear (s)':>15} {'Dict (s)':>15}")
    for row in run_benchmark():
        print(f"{row['size']:>10} {row['linear_seconds']:>15.8f} {row['dict_seconds']:>15.8f}")


if __name__ == "__main__":
    main()
