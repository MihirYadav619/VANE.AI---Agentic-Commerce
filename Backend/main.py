"""
Agentic Commerce - Backend Skeleton (Day 1)
Serves catalog + policy data. Buyer agent, hybrid search, Razorpay
integration, and audit logging will be added in later days.
"""

import json
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

BASE_DIR = Path(__file__).parent
CATALOG_PATH = BASE_DIR / "data" / "catalog.json"
POLICY_PATH = BASE_DIR / "data" / "policy.json"

app = FastAPI(title="Agentic Commerce API", version="0.1.0")

# Allow the React frontend (running on a different port) to call this API.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten this before any real deployment
    allow_methods=["*"],
    allow_headers=["*"],
)


def load_json(path: Path) -> dict:
    if not path.exists():
        raise HTTPException(status_code=500, detail=f"Missing data file: {path.name}")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


@app.get("/")
def root():
    return {"status": "ok", "message": "Agentic Commerce API is running"}


@app.get("/catalog")
def get_catalog():
    """Returns the full product catalog. Later this will be exposed in a
    more agent-friendly retrieval format (hybrid FAISS + BM25 search)."""
    return load_json(CATALOG_PATH)


@app.get("/catalog/product/{product_id}")
def get_product(product_id: str):
    catalog = load_json(CATALOG_PATH)
    for product in catalog["products"]:
        if product["id"] == product_id:
            return product
    raise HTTPException(status_code=404, detail=f"Product {product_id} not found")


@app.get("/policy")
def get_policy():
    """Returns the current bounds/gate policy used by the buyer agent."""
    return load_json(POLICY_PATH)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)