"""Verification (Task 5): confirm gather_requirements extracts sensible
structured criteria from varied buyer requests, live against Ollama.

Run directly: python Python/scripts/spike_gather_requirements.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.agent.requirements import gather_requirements

TEST_MESSAGES = [
    "I need a budget SUV under $25k",
    "looking for a diesel truck, don't care about price",
    "want something sporty, fun to drive, budget around $40k",
    "family sedan, good gas mileage, nothing over 30k",
]


def main():
    for message in TEST_MESSAGES:
        result = gather_requirements(message)
        print(f"--- {message!r}")
        print(f"  max_price:     {result.max_price}")
        print(f"  vehicle_style: {result.vehicle_style}")
        print(f"  fuel_type:     {result.fuel_type}")
        print(f"  must_haves:    {result.must_haves}")
        print()


if __name__ == "__main__":
    main()
