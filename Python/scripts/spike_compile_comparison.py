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

from backend.agent.comparison import compile_comparison, validate_comparison
from backend.agent.requirements import BuyerRequirements
from backend.tools import search_dataset, search_web


def _print_comparison(comparison):
    for car in comparison.cars:
        print(f"\n{car.make} {car.model} ({car.year}) - MSRP: {car.msrp}")
        print(f"  pros: {car.pros}")
        print(f"  cons: {car.cons}")
        print(f"  sources: {car.sources}")
    print(f"\nnotes: {comparison.notes}")


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
    validated_comparison = validate_comparison(raw_comparison, dataset_results)
    _print_comparison(validated_comparison)

    raw_claim_count = sum(len(c.pros) + len(c.cons) for c in raw_comparison.cars)
    validated_claim_count = sum(len(c.pros) + len(c.cons) for c in validated_comparison.cars)
    print(
        f"\n{raw_claim_count - validated_claim_count} claim(s) removed by validate_comparison "
        f"out of {raw_claim_count} total."
    )
    print(
        "If this is 0: either the strengthened prompt alone avoided bad claims this run (LLM output "
        "is non-deterministic — re-run a few times, the original bugs may not reproduce every time), "
        "or the validator missed something — worth reviewing the raw output above by hand either way."
    )

    print("\n=== Degraded-web case (web_results=[]) ===")
    degraded_raw = compile_comparison(requirements, dataset_results, [])
    degraded_validated = validate_comparison(degraded_raw, dataset_results)
    _print_comparison(degraded_validated)

    print("\nManually cross-check remaining pros/cons above against the dataset_results printed at the top.")


if __name__ == "__main__":
    main()
