"""Throwaway spike (Task 1, updated for Task 6): verify ddgs-backed web
search still returns real, current results after search_web moved into
backend/tools.py as a real LangChain @tool.

The actual implementation now lives in backend/tools.py — this script
just re-runs the same live check against the moved version, so it
doubles as Task 6's post-move verification.

Run directly: python Python/scripts/spike_web_search.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.tools import search_web

if __name__ == "__main__":
    query = "2016 Toyota Corolla current market price"
    results = search_web.invoke({"query": query})

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
