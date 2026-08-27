

import json
from pathlib import Path

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

BASE_DIR = Path(__file__).parent.parent / "backend"
CATALOG_PATH = BASE_DIR / "data" / "catalog.json"
INDEX_PATH = BASE_DIR / "data" / "faiss_index.bin"
ID_MAP_PATH = BASE_DIR / "data" / "faiss_id_map.json"

# This model is small (~80MB), fast, and good enough for product search.
# It converts text into a 384-dimensional vector.
MODEL_NAME = "all-MiniLM-L6-v2"


def load_catalog():
    with open(CATALOG_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data["products"]


def build_searchable_text(product):
    """
    Combines the fields that matter for search into one string.
    We include name, category, and description — NOT price/stock/rating,
    since those aren't semantically meaningful for "what is this product".
    """
    return f"{product['name']}. Category: {product['category']}. {product['description']}"


def main():
    print(f"Loading catalog from {CATALOG_PATH}...")
    products = load_catalog()
    print(f"Loaded {len(products)} products.")

    print(f"Loading embedding model ({MODEL_NAME})... this may take a moment on first run.")
    model = SentenceTransformer(MODEL_NAME)

    texts = [build_searchable_text(p) for p in products]
    id_map = [p["id"] for p in products]  # position i in FAISS index -> id_map[i]

    print("Generating embeddings for all products...")
    embeddings = model.encode(texts, show_progress_bar=True, convert_to_numpy=True)
    embeddings = embeddings.astype("float32")  # FAISS requires float32

    # Normalize vectors so we can use inner-product search as cosine similarity.
    faiss.normalize_L2(embeddings)

    dimension = embeddings.shape[1]
    print(f"Embedding dimension: {dimension}")

    # IndexFlatIP = exact search using inner product (cosine similarity,
    # since we normalized). For ~900 products this is instant; no need for
    # an approximate index at this scale.
    index = faiss.IndexFlatIP(dimension)
    index.add(embeddings)

    print(f"Saving FAISS index to {INDEX_PATH}...")
    faiss.write_index(index, str(INDEX_PATH))

    print(f"Saving ID mapping to {ID_MAP_PATH}...")
    with open(ID_MAP_PATH, "w", encoding="utf-8") as f:
        json.dump(id_map, f)

    print(f"\nDone. Indexed {index.ntotal} products.")


if __name__ == "__main__":
    main()