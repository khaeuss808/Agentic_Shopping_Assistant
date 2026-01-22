from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Tuple, Any, Dict, List, Optional


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


# what is a search result
@dataclass
class SearchResult:
    item: Dict[str, Any]
    score: float
    matched_terms: List[str]


@dataclass
class Constraints:
    budget_max: Optional[float] = None
    colors: Optional[List[str]] = None
    categories: Optional[List[str]] = None


def parse_constraints(query: str) -> Constraints:
    """
    Very lightweight constraint parser for fashion shopping queries.

    Extracts:
      - budget_max: e.g., "under $150", "below 200", "$250 max"
      - colors: simple color word matches
      - categories: based on common fashion keywords
    """
    q = query.lower()

    # ---- budget parsing ----
    budget_max: Optional[float] = None

    # patterns like: under $150, below 200, less than $250, $250 max
    budget_patterns = [
        r"(under|below|less than)\s*\$?\s*(\d+)",
        r"\$?\s*(\d+)\s*(max|maximum|or less)",
    ]
    for pat in budget_patterns:
        m = re.search(pat, q)
        if m:
            # number is last captured group that is digits
            nums = re.findall(r"\d+", m.group(0))
            if nums:
                budget_max = float(nums[-1])
                break

    # ---- color parsing ----
    known_colors = [
        "black",
        "white",
        "ivory",
        "cream",
        "beige",
        "camel",
        "brown",
        "gray",
        "grey",
        "charcoal",
        "navy",
        "blue",
        "light blue",
        "green",
        "emerald",
        "burgundy",
        "red",
        "pink",
        "purple",
        "silver",
        "gold",
    ]

    found_colors: List[str] = []
    for c in known_colors:
        # allow "grey" and "gray" variants, basic substring match is fine here
        if c in q:
            found_colors.append(c)

    colors = sorted(set(found_colors)) if found_colors else None

    # ---- category parsing ----
    # Map common words to your catalog categories
    category_map = {
        "dress": "dress",
        "gown": "dress",
        "slip dress": "dress",
        "heels": "shoes",
        "boots": "shoes",
        "shoes": "shoes",
        "sandals": "shoes",
        "clutch": "bag",
        "bag": "bag",
        "purse": "bag",
        "coat": "outerwear",
        "jacket": "outerwear",
        "blouse": "top",
        "top": "top",
        "trousers": "bottom",
        "pants": "bottom",
        "earrings": "accessory",
        "tights": "accessory",
        "accessories": "accessory",
    }

    found_categories: List[str] = []
    # check longer phrases first so "slip dress" hits before "dress"
    for key in sorted(category_map.keys(), key=len, reverse=True):
        if key in q:
            found_categories.append(category_map[key])

    categories = sorted(set(found_categories)) if found_categories else None

    return Constraints(budget_max=budget_max, colors=colors, categories=categories)


def filter_results(
    results: List[SearchResult],
    constraints: Constraints,
) -> List[SearchResult]:
    """
    Apply hard constraints to search results.
    - budget_max: removes items with price > budget_max
    - colors: keeps items that have at least one requested color
    - categories: keeps items whose category matches one of the requested categories
    """
    filtered: List[SearchResult] = []

    for r in results:
        item = r.item

        # budget
        if constraints.budget_max is not None:
            price = float(item.get("price_usd", 10**9))
            if price > constraints.budget_max:
                continue

        # categories
        if constraints.categories:
            if item.get("category") not in constraints.categories:
                continue

        # colors
        if constraints.colors:
            item_colors = set((item.get("colors") or []))
            # normalize a bit
            item_colors_norm = set([c.lower() for c in item_colors])
            want_norm = set([c.lower() for c in constraints.colors])
            if item_colors_norm.isdisjoint(want_norm):
                continue

        filtered.append(r)

    return filtered


# the actual tool
def search_catalog(
    query: str,  # natural language user request
    catalog: Optional[
        List[Dict[str, Any]]
    ] = None,  # optional preloaded data, i think we will take out
    top_k: int = 8,  # how many results to return
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
    # prep the query
    # if user gives empty input --> no results
    q_tokens = _tokenize(query)
    if not q_tokens:
        return []

    results: List[SearchResult] = []
    # loop over all catalog items
    for item in catalog:
        fields = []
        fields.append(item.get("title", ""))
        fields.append(item.get("description", ""))
        fields.append(item.get("brand", ""))
        fields.append(item.get("category", ""))
        fields.extend(item.get("style_tags", []) or [])
        fields.extend(item.get("colors", []) or [])
        # concatenate semantic things into one searchable blob
        haystack = " ".join(str(x) for x in fields).lower()
        h_tokens = set(_tokenize(haystack))  # all unique words describing the product

        # match query tokens to product tokens
        matched = [t for t in q_tokens if t in h_tokens]
        if not matched:
            continue

        # Simple score: matches + title boost
        # how many query words appear in the title
        # bc title matches are more important than description matches
        title_tokens = set(_tokenize(item.get("title", "")))
        title_matches = sum(1 for t in q_tokens if t in title_tokens)

        # number of unique query matches, 0.5 boost for title matches
        score = float(len(set(matched))) + 0.5 * float(title_matches)

        # collect results
        results.append(
            SearchResult(item=item, score=score, matched_terms=sorted(set(matched)))
        )

    # Sort by score desc then rating desc then price asc
    def _sort_key(r: SearchResult):
        rating = r.item.get("rating", 0)
        price = r.item.get("price_usd", 10**9)
        return (r.score, rating, -price)  # higher score, higher rating, lower price

    results.sort(key=_sort_key, reverse=True)
    return results[:top_k]
