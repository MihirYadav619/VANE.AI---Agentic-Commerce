"""
Agentic Commerce - Backend API
Serves catalog + policy data, handles real authentication, and exposes
the full buyer-agent pipeline (policy_engine.py) via /order endpoints,
cart-nudge, and the audit trail.
"""

import sys
import json
from pathlib import Path

from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware

BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent

from auth import init_auth_db, create_user, authenticate_user, create_session, get_user_from_token

sys.path.insert(0, str(PROJECT_ROOT / "buyer-agent"))
sys.path.insert(0, str(PROJECT_ROOT / "audit-service"))

from policy_engine import PolicyEngine
from cart_nudge import get_cart_nudge
from audit_db import get_recent_activity, get_session_history, get_recent_transactions

CATALOG_PATH = BASE_DIR / "data" / "catalog.json"
POLICY_PATH = BASE_DIR / "data" / "policy.json"

app = FastAPI(title="Agentic Commerce API", version="0.6.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

init_auth_db()

print("Initializing policy engine (this may take a moment)...")
engine = PolicyEngine()
print("Policy engine ready.")


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
    return load_json(POLICY_PATH)


# ---------- Authentication ----------

@app.post("/auth/signup")
def signup(payload: dict):
    username = payload.get("username")
    password = payload.get("password")
    if not username or not password:
        raise HTTPException(status_code=400, detail="Username and password required")
    try:
        create_user(username, password)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    token = create_session(username)
    return {"token": token, "username": username}


@app.post("/auth/login")
def login(payload: dict):
    username = payload.get("username")
    password = payload.get("password")
    if not authenticate_user(username, password):
        raise HTTPException(status_code=401, detail="Invalid username or password")
    token = create_session(username)
    return {"token": token, "username": username}


@app.get("/auth/me")
def get_me(authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")
    token = authorization.replace("Bearer ", "")
    username = get_user_from_token(token)
    if not username:
        raise HTTPException(status_code=401, detail="Invalid or expired session")
    return {"username": username}


# ---------- Buyer Agent Pipeline ----------

@app.post("/order/build")
def build_order_endpoint(payload: dict):
    query = payload.get("query")
    mode = payload.get("mode", "browse")
    addons_opted_in = payload.get("addons_opted_in", False)
    addons_budget = payload.get("addons_budget", 0)

    if not query:
        raise HTTPException(status_code=400, detail="Query is required")

    return engine.build_order(query, mode, addons_opted_in, addons_budget)


@app.post("/order/approve")
def approve_order_endpoint(payload: dict):
    order_items = payload.get("order_items")
    order_total = payload.get("order_total")
    session_id = payload.get("session_id")

    if not order_items or not order_total or not session_id:
        raise HTTPException(status_code=400, detail="order_items, order_total, and session_id are required")

    return engine.approve_pending_order(order_items, order_total, session_id)


@app.post("/order/finalize")
def finalize_order_endpoint(payload: dict):
    main_product_id = payload.get("main_product_id")
    addon_ids = payload.get("addon_ids", [])
    session_id = payload.get("session_id")

    if not main_product_id or not session_id:
        raise HTTPException(status_code=400, detail="main_product_id and session_id are required")

    return engine.finalize_selection(main_product_id, addon_ids, session_id)


@app.post("/order/checkout-cart")
def checkout_cart_endpoint(payload: dict):
    product_ids = payload.get("product_ids", [])
    session_id = payload.get("session_id")

    if not product_ids or not session_id:
        raise HTTPException(status_code=400, detail="product_ids and session_id are required")

    return engine.checkout_cart(product_ids, session_id)


# ---------- Cart-Value Nudge ----------

@app.post("/cart/nudge")
def cart_nudge_endpoint(payload: dict):
    cart_total = payload.get("cart_total", 0)
    return get_cart_nudge(cart_total)


# ---------- Audit Trail ----------

@app.get("/audit/recent")
def get_recent_audit(limit: int = 30):
    return get_recent_activity(limit=limit)


@app.get("/audit/session/{session_id}")
def get_audit_session(session_id: str):
    return get_session_history(session_id)


@app.get("/audit/recent-orders")
def get_recent_orders(limit: int = 10):
    return get_recent_transactions(limit=limit)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)