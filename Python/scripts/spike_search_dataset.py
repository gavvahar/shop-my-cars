"""Verification (Task 4): confirm search_dataset returns correctly
filtered results against the live cars table.

Run directly: python Python/scripts/spike_search_dataset.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.tools import search_dataset


def main():
    print("--- Budget SUV under $25k ---")
    results = search_dataset.invoke({"max_price": 25000, "vehicle_style": "SUV"})
    print(f"{len(results)} results")
    for car in results[:5]:
        print(f"  {car['make']} {car['model']} ({car['year']}) - ${car['msrp']:,} - {car['vehicle_style']}")
    assert all(car["msrp"] <= 25000 for car in results), "found a result over budget"
    assert all("suv" in car["vehicle_style"].lower() for car in results), "found a non-SUV result"

    print("\n--- Diesel cars, no price cap ---")
    results = search_dataset.invoke({"fuel_type": "diesel"})
    print(f"{len(results)} results")
    for car in results[:5]:
        print(f"  {car['make']} {car['model']} ({car['year']}) - {car['engine_fuel_type']}")
    assert all("diesel" in car["engine_fuel_type"].lower() for car in results), "found a non-diesel result"

    print("\n--- No filters (sanity check on default limit) ---")
    results = search_dataset.invoke({})
    print(f"{len(results)} results (expect <= 15)")
    assert len(results) <= 15

    print("\nAll checks passed.")


if __name__ == "__main__":
    main()
