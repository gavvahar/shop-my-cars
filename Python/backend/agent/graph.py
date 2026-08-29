import logging, sqlite3
from contextlib import closing, contextmanager
from typing import TypedDict

from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, StateGraph
from langgraph.types import interrupt

from .comparison import CarComparison, apply_authoritative_specs, compile_comparison, validate_comparison
from .requirements import BuyerRequirements, gather_requirements, validate_requirements
from ..shortlists import DB_PATH as SHORTLISTS_DB_PATH, save_shortlist
from ..tools import search_dataset, search_web

logger = logging.getLogger(__name__)

CHECKPOINT_DB_PATH = SHORTLISTS_DB_PATH.parent / "checkpoints.db"

# State holds live Pydantic objects (BuyerRequirements, CarComparison) directly.
# Without an explicit allow-list, LangGraph's msgpack serde deserializes them via
# a fallback that logs a deprecation warning and will be blocked in a future version.
CHECKPOINT_ALLOWED_MSGPACK_MODULES = [
    ("backend.agent.requirements", "BuyerRequirements"),
    ("backend.agent.comparison", "CarComparison"),
]


@contextmanager
def open_checkpointer(db_path=CHECKPOINT_DB_PATH):
    """Open a persistent SQLite checkpointer. Caller keeps the `with` block open
    for as long as the graph built against it is in use (e.g. app lifetime)."""
    serde = JsonPlusSerializer(allowed_msgpack_modules=CHECKPOINT_ALLOWED_MSGPACK_MODULES)
    with closing(sqlite3.connect(str(db_path), check_same_thread=False)) as conn:
        checkpointer = SqliteSaver(conn, serde=serde)
        checkpointer.setup()
        yield checkpointer


GraphState = TypedDict(
    "GraphState",
    {
        "buyer_message": str,
        "thread_id": str,
        "requirements": BuyerRequirements,
        "dataset_results": list,
        "web_results": list,
        "comparison": CarComparison,
        "human_decision": str,
        "refinement_text": str,
        "summary": str,
        "search_relaxed_note": str,
        "web_degraded_note": str,
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

    relaxed_note = ""
    if not results:
        if requirements.fuel_type:
            results = search_dataset.invoke({"max_price": requirements.max_price, "vehicle_style": requirements.vehicle_style, "fuel_type": None})
            if results:
                relaxed_note = f"No exact match for fuel type '{requirements.fuel_type}' — showing results without that filter."
        elif requirements.vehicle_style:
            results = search_dataset.invoke({"max_price": requirements.max_price, "vehicle_style": None, "fuel_type": requirements.fuel_type})
            if results:
                relaxed_note = f"No exact match for vehicle style '{requirements.vehicle_style}' — showing results without that filter."

    return {"dataset_results": results, "search_relaxed_note": relaxed_note}


def route_after_search_dataset(state):
    if not state["dataset_results"]:
        return "no_results"
    return "search_web"


def no_results_node(state):
    requirements = state["requirements"]
    summary = (
        f"I couldn't find any cars matching your requirements (max price: {requirements.max_price}, "
        f"style: {requirements.vehicle_style}, fuel type: {requirements.fuel_type}), even after relaxing "
        "one of the filters. Try adjusting your budget or criteria and starting a new search."
    )
    return {"summary": summary}


def _search_web_with_retry(query):
    for attempt in range(2):
        try:
            return search_web.invoke({"query": query})
        except Exception as err:
            logger.warning(f"search_web failed for query '{query}' (attempt {attempt + 1}/2): {err}")
    return []


def search_web_node(state):
    dataset_results = state.get("dataset_results", [])
    top_candidates = dataset_results[:3]

    if not top_candidates:
        return {"web_results": []}

    all_results = []
    any_failed = False
    for car in top_candidates:
        query = f"{car['year']} {car['make']} {car['model']} current market price"
        results = _search_web_with_retry(query)
        if not results:
            any_failed = True
        all_results.extend(results)

    web_degraded_note = ""
    if not all_results:
        web_degraded_note = "Live pricing unavailable — showing dataset specs only."
    elif any_failed:
        web_degraded_note = "Live pricing was unavailable for some vehicles."

    return {"web_results": all_results, "web_degraded_note": web_degraded_note}


def compile_comparison_node(state):
    raw = compile_comparison(state["requirements"], state["dataset_results"], state["web_results"])
    validated = validate_comparison(raw, state["dataset_results"], state["web_results"])
    finalized = apply_authoritative_specs(validated, state["dataset_results"])

    extra_notes = " ".join(note for note in [state.get("search_relaxed_note", ""), state.get("web_degraded_note", "")] if note)
    if extra_notes:
        notes = (finalized.notes + " " if finalized.notes else "") + extra_notes
        finalized = finalized.model_copy(update={"notes": notes})

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
    if state["human_decision"] == "save":
        return "confirm_save"
    return "finalize_handoff"


def confirm_save_node(state):
    decision = interrupt(
        {
            "type": "confirm_save",
            "comparison": state["comparison"].model_dump(),
            "message": "About to permanently save this shortlist. Confirm?",
        }
    )
    return {"human_decision": decision.get("action", "decline")}


def route_after_confirm_save(state):
    if state["human_decision"] == "confirm":
        return "save_shortlist"
    return "finalize_handoff"


def save_shortlist_node(state):
    save_shortlist(state["thread_id"], state["requirements"], state["comparison"])
    return {}


def finalize_handoff_node(state):
    comparison = state["comparison"]
    summary = (
        f"Research complete — {len(comparison.cars)} car(s) compared. This summary is for your reference; no purchase or seller contact has been made. {comparison.notes}"
    ).strip()
    return {"summary": summary}


def build_graph(checkpointer):
    graph = StateGraph(GraphState)

    graph.add_node("gather_requirements", gather_requirements_node)
    graph.add_node("confirm_requirements", confirm_requirements_node)
    graph.add_node("search_dataset", search_dataset_node)
    graph.add_node("no_results", no_results_node)
    graph.add_node("search_web", search_web_node)
    graph.add_node("compile_comparison", compile_comparison_node)
    graph.add_node("human_review", human_review_node)
    graph.add_node("confirm_save", confirm_save_node)
    graph.add_node("save_shortlist", save_shortlist_node)
    graph.add_node("finalize_handoff", finalize_handoff_node)

    graph.set_entry_point("gather_requirements")
    graph.add_edge("gather_requirements", "confirm_requirements")
    graph.add_conditional_edges(
        "confirm_requirements",
        route_after_confirm,
        {"search_dataset": "search_dataset", "gather_requirements": "gather_requirements"},
    )
    graph.add_conditional_edges(
        "search_dataset",
        route_after_search_dataset,
        {"search_web": "search_web", "no_results": "no_results"},
    )
    graph.add_edge("no_results", END)
    graph.add_edge("search_web", "compile_comparison")
    graph.add_edge("compile_comparison", "human_review")
    graph.add_conditional_edges(
        "human_review",
        route_after_review,
        {
            "finalize_handoff": "finalize_handoff",
            "gather_requirements": "gather_requirements",
            "confirm_save": "confirm_save",
        },
    )
    graph.add_conditional_edges(
        "confirm_save",
        route_after_confirm_save,
        {"save_shortlist": "save_shortlist", "finalize_handoff": "finalize_handoff"},
    )
    graph.add_edge("save_shortlist", "finalize_handoff")
    graph.add_edge("finalize_handoff", END)

    return graph.compile(checkpointer=checkpointer)
