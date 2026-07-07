from typing import Any


def build_search_query(query: str) -> dict[str, Any]:
    return {
        "match": {
            "text": {
                "query": query,
            }
        }
    }
