"""Verification (Task 7, refined): confirm compile_comparison's raw output,
run through validate_comparison, no longer contains claims that don't
trace back to real dataset_results rows — specifically checking that
neither the city/highway MPG swap nor the cross-year data-mixing bug
found in the first live run survives uncaught.

Run directly: python Python/scripts/spike_compile_comparison.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.agent.comparison import apply_authoritative_specs, compile_comparison, validate_comparison
from backend.agent.requirements import BuyerRequirements
from backend.tools import search_dataset, search_web


def _print_comparison(comparison):
    for car in comparison.cars:
        print(f"\n{car.make} {car.model} ({car.year}) - MSRP: {car.msrp}")
        print(f"  highway_mpg: {car.highway_mpg}, city_mpg: {car.city_mpg}, hp: {car.horsepower}")
        print(f"  pros: {car.pros}")
        print(f"  cons: {car.cons}")
        print(f"  sources: {car.sources}")
    print(f"\nnotes: {comparison.notes}")


def _check_authoritative_specs(comparison, dataset_results):
    for car in comparison.cars:
        source_rows = [row for row in dataset_results if row["make"].lower() == car.make.lower() and row["model"].lower() == car.model.lower() and row["year"] == car.year]
        if not source_rows:
            print(f"  {car.make} {car.model} ({car.year}): NO MATCHING ROW (should already be dropped)")
            continue
        primary_row = source_rows[0]
        matches = (
            car.msrp == primary_row.get("msrp")
            and car.highway_mpg == primary_row.get("highway_mpg")
            and car.city_mpg == primary_row.get("city_mpg")
            and car.horsepower == primary_row.get("engine_hp")
        )
        print(f"  {car.make} {car.model} ({car.year}): {'OK' if matches else 'MISMATCH'}")


def main():
    requirements = BuyerRequirements(max_price=25000, vehicle_style="SUV", fuel_type=None, must_haves=[])

    dataset_results = search_dataset.invoke({"max_price": 25000, "vehicle_style": "SUV"})
    print(f"dataset_results: {len(dataset_results)} cars")
    for car in dataset_results:
        print(f"  {car}")

    web_results = search_web.invoke({"query": "affordable SUV under $25,000 current market price 2026"})
    print(f"\nweb_results: {len(web_results)} results")
    for result in web_results:
        print(f"  {result}")

    print("\n=== RAW compile_comparison output (before validate_comparison) ===")
    raw_comparison = compile_comparison(requirements, dataset_results, web_results)
    _print_comparison(raw_comparison)

    print("\n=== AFTER validate_comparison ===")
    validated_comparison = validate_comparison(raw_comparison, dataset_results, web_results)
    _print_comparison(validated_comparison)

    print("\n=== AFTER apply_authoritative_specs ===")
    final_comparison = apply_authoritative_specs(validated_comparison, dataset_results)
    _print_comparison(final_comparison)

    print("\n=== Trivial correctness check: typed fields vs. source rows ===")
    _check_authoritative_specs(final_comparison, dataset_results)

    raw_claim_count = sum(len(c.pros) + len(c.cons) for c in raw_comparison.cars)
    validated_claim_count = sum(len(c.pros) + len(c.cons) for c in validated_comparison.cars)
    print(f"\n{raw_claim_count - validated_claim_count} claim(s) removed by validate_comparison out of {raw_claim_count} total.")
    print(
        "If this is 0: either the strengthened prompt alone avoided bad claims this run (LLM output "
        "is non-deterministic — re-run a few times, the original bugs may not reproduce every time), "
        "or the validator missed something — worth reviewing the raw output above by hand either way."
    )

    print("\n=== Degraded-web case (web_results=[]) ===")
    degraded_raw = compile_comparison(requirements, dataset_results, [])
    degraded_validated = validate_comparison(degraded_raw, dataset_results, [])
    degraded_final = apply_authoritative_specs(degraded_validated, dataset_results)
    _print_comparison(degraded_final)

    print(
        "Manually cross-check remaining pros/cons above against the dataset_results/web_results "
        "printed earlier — specifically: (1) every dollar figure traces to either the car's real "
        "MSRP or a real web result price, (2) every source URL actually appears in web_results' "
        "url field, not just a plausible-looking invented one. This is now a standing check, not "
        "a one-off — both fabrication classes (wrong-row numbers, invented URLs/prices) have shown "
        "up in real runs."
    )


if __name__ == "__main__":
    main()
