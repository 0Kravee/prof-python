"""Plain Python DB-API (sqlite3) access, without the ORM.

Only the SQL text is built by the program; every value goes through
``?`` placeholders (parameterized queries), so SQL injection is impossible.
"""

import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any

SELECT_CARS = """
SELECT manufacturers.name AS manufacturer,
       cars.model, cars.year, cars.price, cars.mileage, cars.vin
FROM cars
JOIN manufacturers ON cars.manufacturer_id = manufacturers.id
"""


def find_cars_by_manufacturer(
    database_path: str | Path, manufacturer: str
) -> list[dict[str, Any]]:
    """Cars of one manufacturer (case-insensitive), parameterized."""
    query = SELECT_CARS + (
        "WHERE LOWER(manufacturers.name) = LOWER(?) ORDER BY cars.id"
    )
    with closing(sqlite3.connect(database_path)) as connection:
        connection.row_factory = sqlite3.Row
        cursor = connection.cursor()
        cursor.execute(query, (manufacturer.strip(),))
        return [dict(row) for row in cursor.fetchall()]


def search_cars(
    database_path: str | Path,
    manufacturer: str | None = None,
    model: str | None = None,
    min_year: int | None = None,
) -> list[dict[str, Any]]:
    """Optional criteria; fixed SQL fragments + bound parameters."""
    conditions: list[str] = []
    params: list[Any] = []
    if manufacturer is not None:
        conditions.append("LOWER(manufacturers.name) = LOWER(?)")
        params.append(manufacturer.strip())
    if model is not None:
        conditions.append("LOWER(cars.model) = LOWER(?)")
        params.append(model.strip())
    if min_year is not None:
        conditions.append("cars.year >= ?")
        params.append(min_year)
    query = SELECT_CARS
    if conditions:
        query += "WHERE " + " AND ".join(conditions) + "\n"
    query += "ORDER BY cars.id"
    with closing(sqlite3.connect(database_path)) as connection:
        connection.row_factory = sqlite3.Row
        cursor = connection.cursor()
        cursor.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]


def count_cars_by_manufacturer(
    database_path: str | Path,
) -> list[tuple[str, int]]:
    """GROUP BY example through DB-API."""
    query = """
    SELECT manufacturers.name, COUNT(cars.id)
    FROM manufacturers
    LEFT JOIN cars ON cars.manufacturer_id = manufacturers.id
    GROUP BY manufacturers.id, manufacturers.name
    ORDER BY manufacturers.name
    """
    with closing(sqlite3.connect(database_path)) as connection:
        cursor = connection.cursor()
        cursor.execute(query)
        return [(name, int(count)) for name, count in cursor.fetchall()]
