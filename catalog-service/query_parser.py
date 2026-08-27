"""
Phase 2 - Step 2b: Parse price constraints out of a natural-language query
before it reaches BM25/FAISS.

Why this exists: words like "under", "below", "5000" get treated as plain
keywords by BM25, which can accidentally match unrelated things (e.g. the
brand name "UNDER ARMOUR" matching the word "under" in "watch under 5000").
Price is a numeric constraint, not a keyword — it should be extracted and
applied as a structured filter, not left in the search text.
"""

import re

# Patterns are checked in order; the first one that matches wins.
# Each pattern captures a number (with optional commas, e.g. "10,000").
PRICE_PATTERNS = [
    (r"\bunder\s*(?:rs\.?|inr|₹)?\s*(\d[\d,]*)", "max"),
    (r"\bbelow\s*(?:rs\.?|inr|₹)?\s*(\d[\d,]*)", "max"),
    (r"\bless than\s*(?:rs\.?|inr|₹)?\s*(\d[\d,]*)", "max"),
    (r"\bover\s*(?:rs\.?|inr|₹)?\s*(\d[\d,]*)", "min"),
    (r"\babove\s*(?:rs\.?|inr|₹)?\s*(\d[\d,]*)", "min"),
    (r"\bmore than\s*(?:rs\.?|inr|₹)?\s*(\d[\d,]*)", "min"),
    (r"\bbetween\s*(?:rs\.?|inr|₹)?\s*(\d[\d,]*)\s*(?:and|to|-)\s*(?:rs\.?|inr|₹)?\s*(\d[\d,]*)", "range"),
]


def parse_price_constraint(query):
    """
    Extracts a price constraint from a query string, if present.

    Returns a tuple: (cleaned_query, constraint)
      - cleaned_query: the original query with the price phrase removed
      - constraint: a dict like {"max": 5000} or {"min": 2000} or
        {"min": 1000, "max": 3000}, or None if no price phrase was found

    Examples:
      "watch under 5000"        -> ("watch", {"max": 5000})
      "kurta above 1000"        -> ("kurta", {"min": 1000})
      "jacket between 2000 and 5000" -> ("jacket", {"min": 2000, "max": 5000})
      "blue denim jacket"       -> ("blue denim jacket", None)
    """
    query_lower = query.lower()

    for pattern, kind in PRICE_PATTERNS:
        match = re.search(pattern, query_lower)
        if not match:
            continue

        cleaned_query = query_lower[: match.start()] + query_lower[match.end():]
        cleaned_query = re.sub(r"\s+", " ", cleaned_query).strip()

        if kind == "range":
            low = int(match.group(1).replace(",", ""))
            high = int(match.group(2).replace(",", ""))
            constraint = {"min": min(low, high), "max": max(low, high)}
        else:
            value = int(match.group(1).replace(",", ""))
            constraint = {kind: value}

        return cleaned_query, constraint

    # No price phrase found — return the query unchanged.
    return query, None


def apply_price_filter(results, constraint, get_price_fn):
    """
    Filters a list of search results using a structured price constraint.

    results: list of items (e.g. (product_id, score) tuples)
    constraint: dict like {"max": 5000}, or None
    get_price_fn: function that takes a result item and returns its price
                  (needed because different search functions return
                  different tuple shapes)
    """
    if constraint is None:
        return results

    filtered = []
    for item in results:
        price = get_price_fn(item)
        if "min" in constraint and price < constraint["min"]:
            continue
        if "max" in constraint and price > constraint["max"]:
            continue
        filtered.append(item)
    return filtered


if __name__ == "__main__":
    test_queries = [
        "watch under 5000",
        "kurta above 1000",
        "jacket between 2000 and 5000",
        "blue denim jacket",
        "shirt below rs. 800",
    ]
    for q in test_queries:
        cleaned, constraint = parse_price_constraint(q)
        print(f"'{q}'  ->  cleaned: '{cleaned}'  |  constraint: {constraint}")