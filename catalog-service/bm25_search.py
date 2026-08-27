"""
Phase 2 - Step 2: BM25 keyword search over the catalog.

Unlike FAISS (which needs a pre-built index file), BM25 is lightweight
enough to build fresh in memory every time the backend starts — no
separate "build" script needed, unlike build_embeddings.py.

This file defines a reusable function; it doesn't run standalone in
production, but has a small __main__ block at the bottom so you can test
it directly.
"""

import json
import re
from pathlib import Path

from rank_bm25 import BM25Okapi

BASE_DIR = Path(__file__).parent.parent / "backend"
CATALOG_PATH = BASE_DIR / "data" / "catalog.json"


def load_catalog():
    with open(CATALOG_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data["products"]


def tokenize(text):
    """
    BM25 works on lists of words ("tokens"), not raw strings. This is a
    simple tokenizer: lowercase everything, strip punctuation, split on
    whitespace. Good enough for product names/descriptions.
    """
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return text.split()


def build_searchable_text(product):
    # Same field choice as FAISS, for consistency between the two search methods.
    return f"{product['name']} {product['category']} {product['description']}"


class CatalogBM25Search:
    """
    Wraps rank_bm25 with our catalog so callers can just do:
        searcher = CatalogBM25Search()
        results = searcher.search("blue denim jacket", top_k=5)
    """

    def __init__(self):
        self.products = load_catalog()
        self.id_map = [p["id"] for p in self.products]  # position -> product id
        tokenized_corpus = [tokenize(build_searchable_text(p)) for p in self.products]
        self.bm25 = BM25Okapi(tokenized_corpus)

    def search(self, query, top_k=10):
        """
        Returns a list of (product_id, bm25_score) tuples, sorted by
        score descending. Scores are NOT normalized (BM25 scores can be
        any positive number) — normalization happens later when we
        combine this with FAISS scores.
        """
        tokenized_query = tokenize(query)
        scores = self.bm25.get_scores(tokenized_query)

        # Pair each score with its product id, then sort descending.
        ranked = sorted(zip(self.id_map, scores), key=lambda x: x[1], reverse=True)
        return ranked[:top_k]


if __name__ == "__main__":
    # Quick manual test — run this file directly to try a few queries.
    from query_parser import parse_price_constraint, apply_price_filter

    searcher = CatalogBM25Search()

    test_queries = ["blue denim jacket", "watch under 5000", "cotton kurta"]
    for q in test_queries:
        cleaned_query, price_constraint = parse_price_constraint(q)
        print(f"\nQuery: '{q}'  ->  searching for: '{cleaned_query}'  |  price filter: {price_constraint}")

        results = searcher.search(cleaned_query, top_k=10)  # get more, then filter

        if price_constraint:
            get_price = lambda item: next(p["price"] for p in searcher.products if p["id"] == item[0])
            results = apply_price_filter(results, price_constraint, get_price)

        for pid, score in results[:3]:
            product = next(p for p in searcher.products if p["id"] == pid)
            print(f"  [{score:.2f}] {pid} - {product['name']} (₹{product['price']})")