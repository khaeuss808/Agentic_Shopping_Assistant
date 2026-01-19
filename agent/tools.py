from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional


CATALOG_PATH = Path("data/product_catalog.json")


def load_catalog(path: Path = CATALOG_PATH) -> List[Dict[str, Any]]:
    """Load product catalog from JSON. returns list of product dictionaries"""
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _tokenize(text: str) -> List[str]:
    """Simple tokenizer for keyword matching.
    Would split "Winter wedding dress!" to
    ['winter', 'wedding', 'dress']
        lower case and no punctuation
    """
    text = text.lower()
    # Keep words/numbers, split on non-alphanum
    tokens = re.findall(r"[a-z0-9]+", text)
    return tokens


@dataclass
class SearchResult:
    item: Dict[str, Any]
    score: float
    matched_terms: List[str]


# the actual tool
def search_catalog(
    query: str,
    catalog: Optional[List[Dict[str, Any]]] = None,
    top_k: int = 8,
) -> List[SearchResult]:
    """
    Baseline keyword search over catalog.
    going to just try and see if it works

    Scoring:
      - counts query token matches across title/description/style_tags/category/brand/colors
      - mild boosts for title matches
    """
    if catalog is None:
        catalog = load_catalog()

    q_tokens = _tokenize(query)
    if not q_tokens:
        return []

    results: List[SearchResult] = []

    for item in catalog:
        fields = []
        fields.append(item.get("title", ""))
        fields.append(item.get("description", ""))
        fields.append(item.get("brand", ""))
        fields.append(item.get("category", ""))
        fields.extend(item.get("style_tags", []) or [])
        fields.extend(item.get("colors", []) or [])
        haystack = " ".join(str(x) for x in fields).lower()
        h_tokens = set(_tokenize(haystack))

        matched = [t for t in q_tokens if t in h_tokens]
        if not matched:
            continue

        # Simple score: matches + title boost
        title_tokens = set(_tokenize(item.get("title", "")))
        title_matches = sum(1 for t in q_tokens if t in title_tokens)

        score = float(len(set(matched))) + 0.5 * float(title_matches)

        results.append(
            SearchResult(item=item, score=score, matched_terms=sorted(set(matched)))
        )

    # Sort by score desc then rating desc then price asc (nice heuristic)
    def _sort_key(r: SearchResult):
        rating = r.item.get("rating", 0)
        price = r.item.get("price_usd", 10**9)
        return (r.score, rating, -price)  # higher score, higher rating, lower price

    results.sort(key=_sort_key, reverse=True)
    return results[:top_k]
