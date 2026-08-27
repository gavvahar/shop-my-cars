"""Verification (Task 5, refined): confirm gather_requirements +
validate_requirements together produce clean, dataset-safe structured
criteria — real category values only in vehicle_style/fuel_type,
anything unmatched demoted to must_haves instead of silently passed
through to search_dataset (which would return zero results on a bogus
category value).

Run directly: python Python/scripts/spike_gather_requirements.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.agent.requirements import gather_requirements, validate_requirements

TEST_MESSAGES = [
    "I need a budget SUV under $25k",
    "looking for a diesel truck, don't care about price",
    "want something sporty, fun to drive, budget around $40k",
    "family sedan, good gas mileage, nothing over 30k",
]


def _print_requirements(label, requirements):
    print(f"  [{label}]")
    print(f"    max_price:     {requirements.max_price}")
    print(f"    vehicle_style: {requirements.vehicle_style}")
    print(f"    fuel_type:     {requirements.fuel_type}")
    print(f"    must_haves:    {requirements.must_haves}")


def main():
    for message in TEST_MESSAGES:
        print(f"--- {message!r}")
        raw = gather_requirements(message)
        _print_requirements("before validate_requirements", raw)
        validated = validate_requirements(raw)
        _print_requirements("after validate_requirements", validated)
        print()


if __name__ == "__main__":
    main()
