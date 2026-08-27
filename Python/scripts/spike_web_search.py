"""Throwaway spike (Task 1): verify duckduckgo-search returns real,
current results with zero API key/signup.

Run directly: python Python/scripts/spike_web_search.py
"""
import re

try:
    from ddgs import DDGS
except ImportError:
    from duckduckgo_search import DDGS


def search_web(query: str, max_results: int = 5) -> list[dict]:
    """Search the live web for current car pricing/availability info.

    Use this for real-time market data (current asking prices, listings,
    reviews) that the local car specs database can't provide — that
    dataset only has historical MSRP and static specs, not live pricing.

    Args:
        query: A search query, e.g. "2016 Toyota Corolla current market price".
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


if __name__ == "__main__":
    query = "2016 Toyota Corolla current market price"
    results = search_web(query)

    if not results:
        print("No results returned — check the query or package version/API.")
    else:
        for i, result in enumerate(results, start=1):
            print(f"--- Result {i} ---")
            print(f"Title:   {result['title']}")
            print(f"Snippet: {result['snippet']}")
            print(f"URL:     {result['url']}")
            print(f"Price:   {result['price']}")
            print()
