"""Verification (Task 8): run one full manual query through the graph,
confirming both interrupts genuinely pause and resume, and the graph
reaches finalize_handoff with a real, faithful comparison.

Run directly: python Python/scripts/spike_graph.py

NOTE ON API UNCERTAINTY: this is the first use of LangGraph's dynamic
interrupt()/Command(resume=...) pattern in this project — the exact shape
of invoke()'s return when paused (result["__interrupt__"] below) and
Command's import path are from training knowledge, not verified against
the installed langgraph version. If this errors, check `pip show
langgraph` and its current docs/source for the real interrupt-result
shape before assuming the graph logic itself is wrong.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from langgraph.types import Command

from backend.agent.graph import build_graph


def main():
    graph = build_graph()
    config = {"configurable": {"thread_id": "spike-test-1"}}

    print("=== Turn 1: initial invoke ===")
    result = graph.invoke({"buyer_message": "I need a budget SUV under $25k"}, config=config)
    print(f"Paused at interrupt: {result.get('__interrupt__')}")

    print("\n=== Resuming interrupt 1 (confirm_requirements) with 'approve' ===")
    result = graph.invoke(Command(resume={"action": "approve"}), config=config)
    print(f"Paused at interrupt: {result.get('__interrupt__')}")

    print("\n=== Resuming interrupt 2 (human_review) with 'approve' ===")
    result = graph.invoke(Command(resume={"action": "approve"}), config=config)

    print("\n=== Final state ===")
    print(f"summary: {result.get('summary')}")
    comparison = result.get("comparison")
    if comparison:
        for car in comparison.cars:
            print(f"\n{car.make} {car.model} ({car.year})")
            print(f"  pros: {car.pros}")
            print(f"  cons: {car.cons}")
        print(f"\nnotes: {comparison.notes}")
    else:
        print("No comparison in final state — something didn't reach finalize_handoff correctly.")

    print(
        "\nManually confirm: did the graph actually pause twice (not run straight through), "
        "does every dollar figure trace to the car's real MSRP or a real web result price, "
        "and does every source URL actually appear in the search_web results (not a "
        "plausible-looking invented one)?"
    )


if __name__ == "__main__":
    main()
