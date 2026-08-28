from typing import TypedDict

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph
from langgraph.types import interrupt

from .comparison import CarComparison, apply_authoritative_specs, compile_comparison, validate_comparison
from .requirements import BuyerRequirements, gather_requirements, validate_requirements
from ..tools import search_dataset, search_web

GraphState = TypedDict(
    "GraphState",
    {
        "buyer_message": str,
        "requirements": BuyerRequirements,
        "dataset_results": list,
        "web_results": list,
        "comparison": CarComparison,
        "human_decision": str,
        "refinement_text": str,
        "summary": str,
    },
)


def gather_requirements_node(state):
    message = state.get("buyer_message", "")
    refinement = state.get("refinement_text", "")
    if refinement:
        message = f"{message}\n\nAdditional clarification: {refinement}"

    raw = gather_requirements(message)
    validated = validate_requirements(raw)
    return {"requirements": validated, "refinement_text": ""}


def confirm_requirements_node(state):
    decision = interrupt({"type": "confirm_requirements", "requirements": state["requirements"].model_dump()})
    return {
        "human_decision": decision.get("action", "approve"),
        "refinement_text": decision.get("refinement", ""),
    }


def route_after_confirm(state):
    if state["human_decision"] == "refine":
        return "gather_requirements"
    return "search_dataset"


def search_dataset_node(state):
    requirements = state["requirements"]
    results = search_dataset.invoke(
        {
            "max_price": requirements.max_price,
            "vehicle_style": requirements.vehicle_style,
            "fuel_type": requirements.fuel_type,
        }
    )
    return {"dataset_results": results}


def search_web_node(state):
    dataset_results = state.get("dataset_results", [])
    top_candidates = dataset_results[:3]

    if not top_candidates:
        return {"web_results": []}

    all_results = []
    for car in top_candidates:
        query = f"{car['year']} {car['make']} {car['model']} current market price"
        all_results.extend(search_web.invoke({"query": query}))

    return {"web_results": all_results}


def compile_comparison_node(state):
    raw = compile_comparison(state["requirements"], state["dataset_results"], state["web_results"])
    validated = validate_comparison(raw, state["dataset_results"], state["web_results"])
    finalized = apply_authoritative_specs(validated, state["dataset_results"])
    return {"comparison": finalized}


def human_review_node(state):
    decision = interrupt({"type": "human_review", "comparison": state["comparison"].model_dump()})
    return {
        "human_decision": decision.get("action", "approve"),
        "refinement_text": decision.get("refinement", ""),
    }


def route_after_review(state):
    if state["human_decision"] == "refine":
        return "gather_requirements"
    return "finalize_handoff"


def finalize_handoff_node(state):
    comparison = state["comparison"]
    summary = (
        f"Research complete — {len(comparison.cars)} car(s) compared. This summary is for your reference; no purchase or seller contact has been made. {comparison.notes}"
    ).strip()
    return {"summary": summary}


def build_graph():
    graph = StateGraph(GraphState)

    graph.add_node("gather_requirements", gather_requirements_node)
    graph.add_node("confirm_requirements", confirm_requirements_node)
    graph.add_node("search_dataset", search_dataset_node)
    graph.add_node("search_web", search_web_node)
    graph.add_node("compile_comparison", compile_comparison_node)
    graph.add_node("human_review", human_review_node)
    graph.add_node("finalize_handoff", finalize_handoff_node)

    graph.set_entry_point("gather_requirements")
    graph.add_edge("gather_requirements", "confirm_requirements")
    graph.add_conditional_edges(
        "confirm_requirements",
        route_after_confirm,
        {"search_dataset": "search_dataset", "gather_requirements": "gather_requirements"},
    )
    graph.add_edge("search_dataset", "search_web")
    graph.add_edge("search_web", "compile_comparison")
    graph.add_edge("compile_comparison", "human_review")
    graph.add_conditional_edges(
        "human_review",
        route_after_review,
        {"finalize_handoff": "finalize_handoff", "gather_requirements": "gather_requirements"},
    )
    graph.add_edge("finalize_handoff", END)

    checkpointer = MemorySaver()
    return graph.compile(checkpointer=checkpointer)
