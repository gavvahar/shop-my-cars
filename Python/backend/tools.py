import re

from ddgs import DDGS
from langchain_core.tools import tool

from . import db


@tool
def search_dataset(
    max_price: float | None = None,
    vehicle_style: str | None = None,
    fuel_type: str | None = None,
    limit: int = 15,
) -> list[dict]:
    """Search the local car specs database using structured filter criteria.

    Use this when the user's requirements have already been extracted into
    concrete filters (budget, vehicle style, fuel type) — this is a
    structured SQL filter over historical spec/MSRP data, not a natural
    language search. For fuzzy/open-ended questions this filter can't
    answer, or for current market pricing/listings (this dataset only has
    historical MSRP, not live prices), use search_web instead.

    Args:
        max_price: Maximum MSRP in dollars.
        vehicle_style: Vehicle style/body type, e.g. "SUV", "Sedan", "Coupe".
            Partial match, case-insensitive.
        fuel_type: Fuel type, e.g. "regular unleaded", "diesel", "electric".
            Partial match, case-insensitive.
        limit: Maximum number of results to return.

    Returns:
        A list of car dicts (make, model, year, specs, msrp, etc.),
        ordered by price ascending.
    """
    return db.search_cars(max_price=max_price, vehicle_style=vehicle_style, fuel_type=fuel_type, limit=limit)


@tool
def search_web(query: str, max_results: int = 5) -> list[dict]:
    """Search the live web for current car pricing, listings, and reviews.

    Use this for information the local dataset can't provide — current
    market pricing, active listings, recent reviews — since the dataset
    only has historical MSRP and static specs. Works best with a specific
    make/model/year in the query, e.g. "2016 Toyota Corolla current market
    price". For structured filtering over the known dataset (budget,
    vehicle style, fuel type), use search_dataset instead.

    Args:
        query: A search query, ideally including make/model/year.
        max_results: Maximum number of results to return.

    Returns:
        A list of dicts, each with keys "title", "snippet", "url", and
        "price" (first dollar amount found in the snippet, or None).
    """
    with DDGS() as ddgs:
        raw_results = ddgs.text(query, max_results=max_results)

    results = []
    for item in raw_results:
        snippet = item.get("body", "")
        price_match = re.search(r"\$[\d,]+(?:\.\d{2})?", snippet)
        results.append(
            {
                "title": item.get("title", ""),
                "snippet": snippet,
                "url": item.get("href", ""),
                "price": price_match.group(0) if price_match else None,
            }
        )
    return results
