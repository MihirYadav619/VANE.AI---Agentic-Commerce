"""
Phase 2 - Step 3 (revised): Combine FAISS (semantic) and BM25 (keyword)
search using Reciprocal Rank Fusion (RRF), with stock filtering.

Why RRF instead of normalized-score averaging:
Min-max normalization always gives the #1 result in each method a score
of 1.0, regardless of how strong that match actually was. This caused a
weak-but-literal keyword match (e.g. "Jeans" matching "blue"+"denim") to
tie with a genuinely strong semantic match, because both were "#1" in
their respective method. RRF avoids this by scoring based on RANK
POSITION, not raw score magnitude, which is the standard approach used
in production hybrid search systems (Elasticsearch, Weaviate, etc.).
"""

import json
from pathlib import Path

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

from bm25_search import CatalogBM25Search
from query_parser import parse_price_constraint

BASE_DIR = Path(__file__).parent.parent / "backend"
CATALOG_PATH = BASE_DIR / "data" / "catalog.json"
INDEX_PATH = BASE_DIR / "data" / "faiss_index.bin"
ID_MAP_PATH = BASE_DIR / "data" / "faiss_id_map.json"

MODEL_NAME = "all-MiniLM-L6-v2"

# Standard RRF constant. Higher k = flatter weighting across ranks (rank 1
# and rank 10 matter more similarly); lower k = rank 1 dominates much more
# strongly. 60 is the commonly used default in IR research and production
# systems, so we use it rather than inventing our own number.
RRF_K = 60


def load_catalog():
    with open(CATALOG_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data["products"]


def reciprocal_rank_fusion(*ranked_lists):
    """
    Combines any number of ranked (product_id, score) lists into one
    fused ranking using RRF.

    Each input list should already be sorted best-first. We only use the
    POSITION of each id in its list, not the original score value — this
    is the whole point of RRF (rank-based, not magnitude-based fusion).

    Returns: dict of {product_id: fused_score}, higher = better.
    """
    fused_scores = {}
    for ranked_list in ranked_lists:
        for rank, (product_id, _original_score) in enumerate(ranked_list, start=1):
            fused_scores[product_id] = fused_scores.get(product_id, 0.0) + 1.0 / (RRF_K + rank)
    return fused_scores


class HybridSearch:
    """
    Combines FAISS semantic search and BM25 keyword search into one
    RRF-ranked result list, with automatic price-constraint parsing and
    out-of-stock filtering.

    Usage:
        search = HybridSearch()
        results = search.search("comfortable cotton kurta under 2000", top_k=5)
    """

    def __init__(self):
        print("Loading catalog and search indexes...")
        self.products = load_catalog()
        self.products_by_id = {p["id"]: p for p in self.products}

        self.faiss_index = faiss.read_index(str(INDEX_PATH))
        with open(ID_MAP_PATH, "r", encoding="utf-8") as f:
            self.faiss_id_map = json.load(f)
        self.embed_model = SentenceTransformer(MODEL_NAME)

        self.bm25_searcher = CatalogBM25Search()

        print("Hybrid search ready.")

    def _faiss_search(self, query, top_k):
        query_vector = self.embed_model.encode([query], convert_to_numpy=True).astype("float32")
        faiss.normalize_L2(query_vector)

        similarities, indices = self.faiss_index.search(query_vector, top_k)

        results = []
        for sim, idx in zip(similarities[0], indices[0]):
            if idx == -1:
                continue
            product_id = self.faiss_id_map[idx]
            results.append((product_id, float(sim)))
        return results

    def search(self, query, top_k=10, candidate_pool_size=30, include_out_of_stock=False):
        """
        Runs hybrid search (RRF fusion of FAISS + BM25) and returns a
        ranked list of full product dicts.

        include_out_of_stock: False by default — a normal shopping search
        shouldn't surface items that can't actually be bought right now.
        (Phase 9's failure-demo will simulate a stock change happening
        AFTER search/selection, at payment time — not by showing
        out-of-stock items here.)
        """
        cleaned_query, price_constraint = parse_price_constraint(query)

        faiss_results = self._faiss_search(cleaned_query, candidate_pool_size)
        bm25_results = self.bm25_searcher.search(cleaned_query, candidate_pool_size)

        fused_scores = reciprocal_rank_fusion(faiss_results, bm25_results)
        ranked_ids = sorted(fused_scores, key=fused_scores.get, reverse=True)

        results = []
        for pid in ranked_ids:
            product = self.products_by_id.get(pid)
            if product is None:
                continue

            if not include_out_of_stock and product["stock"] == 0:
                continue

            if price_constraint:
                price = product["price"]
                if "min" in price_constraint and price < price_constraint["min"]:
                    continue
                if "max" in price_constraint and price > price_constraint["max"]:
                    continue

            results.append({**product, "match_score": round(fused_scores[pid], 5)})
            if len(results) >= top_k:
                break

        return results


if __name__ == "__main__":
    search = HybridSearch()

    test_queries = [
        "blue denim jacket",
        "watch under 5000",
        "cotton kurta",
        "comfortable formal shirt for office",
    ]

    for q in test_queries:
        print(f"\n{'='*60}\nQuery: '{q}'")
        results = search.search(q, top_k=5)
        for r in results:
            print(f"  [{r['match_score']}] {r['id']} - {r['name']} (₹{r['price']}, stock: {r['stock']})")