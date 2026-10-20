"""Load and query the bundled sample laptop catalog."""

import csv
from pathlib import Path


DEFAULT_CSV_PATH = Path(__file__).parent / "data" / "products.csv"
REQUIRED_COLUMNS = {
    "product_id",
    "name",
    "price_inr",
    "ram_gb",
    "processor",
    "storage",
    "battery_life_hours",
    "rating",
    "features",
    "customer_reviews",
    "data_type",
}
NUMERIC_COLUMNS = ("price_inr", "ram_gb", "battery_life_hours", "rating")
TEXT_COLUMNS = (
    "product_id",
    "name",
    "processor",
    "storage",
    "features",
    "customer_reviews",
    "data_type",
)


def _optional_number(value, column, row_number):
    """Parse a numeric cell, preserving blanks as None."""
    value = value.strip()
    if not value:
        return None
    try:
        return float(value)
    except ValueError as error:
        raise ValueError(
            f"Invalid number in '{column}' on CSV row {row_number}: {value!r}"
        ) from error


def load_products(csv_path=DEFAULT_CSV_PATH):
    """Load products from CSV and validate its columns and cell values.

    Blank optional cells are represented by None. Product IDs, names, and the
    sample-data marker must be present; malformed numeric values raise ValueError.
    """
    with Path(csv_path).open("r", newline="", encoding="utf-8") as csv_file:
        reader = csv.DictReader(csv_file)
        if reader.fieldnames is None:
            raise ValueError("CSV is empty or has no header row")

        missing_columns = REQUIRED_COLUMNS.difference(reader.fieldnames)
        if missing_columns:
            missing = ", ".join(sorted(missing_columns))
            raise ValueError(f"CSV is missing required columns: {missing}")

        products = []
        for row_number, row in enumerate(reader, start=2):
            product = {
                column: (row.get(column) or "").strip() or None
                for column in TEXT_COLUMNS
            }
            if not product["product_id"] or not product["name"]:
                raise ValueError(
                    f"CSV row {row_number} must include product_id and name"
                )
            if product["data_type"] != "sample":
                raise ValueError(
                    f"CSV row {row_number} must be marked data_type='sample'"
                )

            for column in NUMERIC_COLUMNS:
                product[column] = _optional_number(
                    row.get(column) or "", column, row_number
                )
            products.append(product)

    return products


def filter_products(products, max_budget_inr=None, min_ram_gb=None):
    """Return products within an optional budget and minimum RAM constraint."""
    if max_budget_inr is not None and max_budget_inr < 0:
        raise ValueError("max_budget_inr must be non-negative")
    if min_ram_gb is not None and min_ram_gb < 0:
        raise ValueError("min_ram_gb must be non-negative")

    matches = []
    for product in products:
        price = product.get("price_inr")
        ram = product.get("ram_gb")
        if max_budget_inr is not None and (price is None or price > max_budget_inr):
            continue
        if min_ram_gb is not None and (ram is None or ram < min_ram_gb):
            continue
        matches.append(product)
    return matches


def compare_prices(products):
    """Return a new list sorted by INR price, with unknown prices at the end."""
    return sorted(
        products,
        key=lambda product: (
            product.get("price_inr") is None,
            product.get("price_inr") or 0,
        ),
    )
