"""Verification (Task 8): run one full manual query through the graph,
confirming both interrupts genuinely pause and resume, and the graph
reaches finalize_handoff with a real, faithful comparison.

Task 10 extends this with a real persistence check: build the graph
against a persistent SQLite checkpointer, run to the first interrupt,
close the connection, then open a genuinely NEW connection + graph
instance against the same thread_id and confirm state (including the
Pydantic objects in it) survives the boundary.

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

from backend.agent.comparison import CarComparison
from backend.agent.graph import build_graph, open_checkpointer
from backend.agent.requirements import BuyerRequirements
from backend.shortlists import get_shortlists_by_thread


def _run_full_flow(graph, thread_id, buyer_message, review_action, confirm_action=None):
    config = {"configurable": {"thread_id": thread_id}}
    graph.invoke({"buyer_message": buyer_message, "thread_id": thread_id}, config=config)
    graph.invoke(Command(resume={"action": "approve"}), config=config)  # confirm_requirements
    graph.invoke(Command(resume={"action": review_action}), config=config)  # human_review
    if review_action == "save":
        graph.invoke(Command(resume={"action": confirm_action}), config=config)  # confirm_save


def test_save_paths(graph):
    print("=== Save-path test 1: approve (no save requested) ===")
    thread_id = "spike-save-test-approve"
    _run_full_flow(graph, thread_id, "I need a budget SUV under $25k", review_action="approve")
    rows = get_shortlists_by_thread(thread_id)
    print(f"Rows persisted: {len(rows)} (expect 0)")
    assert len(rows) == 0

    print("\n=== Save-path test 2: save + confirm ===")
    thread_id = "spike-save-test-save-confirm"
    _run_full_flow(graph, thread_id, "I need a budget SUV under $25k", review_action="save", confirm_action="confirm")
    rows = get_shortlists_by_thread(thread_id)
    print(f"Rows persisted: {len(rows)} (expect 1)")
    assert len(rows) == 1
    print(f"Persisted row: {rows[0]}")

    print("\n=== Save-path test 3: save + decline at second confirmation ===")
    thread_id = "spike-save-test-save-decline"
    _run_full_flow(graph, thread_id, "I need a budget SUV under $25k", review_action="save", confirm_action="decline")
    rows = get_shortlists_by_thread(thread_id)
    print(f"Rows persisted: {len(rows)} (expect 0)")
    assert len(rows) == 0

    print("\nAll save-path checks passed.")


def test_persistence_across_restart():
    thread_id = "spike-persistence-test"
    config = {"configurable": {"thread_id": thread_id}}

    print("=== Persistence test: process 1 (run to first interrupt) ===")
    with open_checkpointer() as checkpointer:
        graph = build_graph(checkpointer)
        result = graph.invoke({"buyer_message": "I need a budget SUV under $25k", "thread_id": thread_id}, config=config)
        print(f"Paused at interrupt: {result.get('__interrupt__')}")
    # connection closes here — simulates the process exiting

    print("\n=== Persistence test: process 2 (fresh connection + graph instance, same thread_id) ===")
    with open_checkpointer() as checkpointer:
        graph = build_graph(checkpointer)  # genuinely new graph instance, new connection
        result = graph.invoke(Command(resume={"action": "approve"}), config=config)
        print(f"Paused at interrupt: {result.get('__interrupt__')}")

        result = graph.invoke(Command(resume={"action": "approve"}), config=config)
        print(f"\nFinal summary: {result.get('summary')}")

        requirements = result.get("requirements")
        print(f"requirements type: {type(requirements)} (expect BuyerRequirements, not dict)")
        assert isinstance(requirements, BuyerRequirements), (
            "Requirements did not round-trip as a real BuyerRequirements instance — Pydantic serialization through the SQLite checkpointer may not be working as assumed."
        )

        comparison = result.get("comparison")
        print(f"comparison type: {type(comparison)} (expect CarComparison, not dict)")
        assert isinstance(comparison, CarComparison), "Comparison did not round-trip as a real CarComparison instance."

    print("\nPersistence check passed: state survived across a genuinely separate graph/connection instance.")


def main():
    with open_checkpointer() as checkpointer:
        graph = build_graph(checkpointer)
        config = {"configurable": {"thread_id": "spike-test-1"}}

        print("=== Turn 1: initial invoke ===")
        result = graph.invoke({"buyer_message": "I need a budget SUV under $25k", "thread_id": "spike-test-1"}, config=config)
        print(f"Paused at interrupt: {result.get('__interrupt__')}")

        print("\n=== Resuming interrupt 1 (confirm_requirements) with 'approve' ===")
        result = graph.invoke(Command(resume={"action": "approve"}), config=config)
        print(f"Paused at interrupt: {result.get('__interrupt__')}")

        print("\n=== Resuming interrupt 2 (human_review) with 'approve' ===")
        result = graph.invoke(Command(resume={"action": "approve"}), config=config)

        print("\n=== Actual web_results from this run (for source-URL cross-check) ===")
        for r in result.get("web_results", []):
            print(f"  {r['url']}")

        print("\n=== Final state ===")
        print(f"summary: {result.get('summary')}")
        comparison = result.get("comparison")
        dataset_results = result.get("dataset_results", [])
        if comparison:
            for car in comparison.cars:
                print(f"\n{car.make} {car.model} ({car.year})")
                print(f"  msrp: {car.msrp}, highway_mpg: {car.highway_mpg}, city_mpg: {car.city_mpg}, hp: {car.horsepower}")
                print(f"  pros: {car.pros}")
                print(f"  cons: {car.cons}")
                print(f"  sources: {car.sources}")
            print(f"\nnotes: {comparison.notes}")

            print("\n=== Trivial correctness check: typed fields vs. source rows ===")
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
        else:
            print("No comparison in final state — something didn't reach finalize_handoff correctly.")

        print(
            "\nManually confirm: did the graph actually pause twice (not run straight through), "
            "and do pros/cons read as qualitative comparisons rather than restated figures? "
            "(Numeric specs are now code-populated and checked above — no manual number "
            "cross-referencing needed for those anymore.)"
        )

        print("\n\n" + "=" * 60)
        print("Task 9: save_shortlist path verification")
        print("=" * 60)
        test_save_paths(graph)

    print("\n\n" + "=" * 60)
    print("Task 10: persistent checkpointer verification")
    print("=" * 60)
    test_persistence_across_restart()


if __name__ == "__main__":
    main()
