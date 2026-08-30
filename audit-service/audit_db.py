"""
Phase 7 - Audit Trail: SQLite-backed logging of every agent decision,
reasoning step, and transaction outcome across the pipeline.

This is what makes the system genuinely "explainable" and "auditable" as
required by the problem statement — every money-adjacent decision made in
Phases 3-6 gets a permanent, queryable record here, not just a printed
reasoning string that disappears after the script exits.
"""

import sqlite3
import json
from pathlib import Path
from datetime import datetime, timezone

DB_PATH = Path(__file__).parent.parent / "backend" / "data" / "audit.db"


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # lets us access columns by name
    return conn


def init_db():
    """
    Creates the audit-trail schema if it doesn't already exist. Safe to
    call every time the app starts — CREATE TABLE IF NOT EXISTS is a no-op
    if the table already exists.
    """
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = get_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS decisions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            session_id TEXT NOT NULL,
            decision_type TEXT NOT NULL,
            product_ids TEXT,
            reasoning TEXT,
            metadata TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            session_id TEXT NOT NULL,
            status TEXT NOT NULL,
            order_total REAL,
            razorpay_order_id TEXT,
            item_ids TEXT,
            metadata TEXT
        )
    """)
    conn.commit()
    conn.close()


def log_decision(session_id, decision_type, product_ids, reasoning, metadata=None):
    """
    Records a single decision-step (product selection, upsell, complete-
    the-look, similar-items, cart-nudge, bandit-refinement, etc.)

    decision_type: a short label like "main_selection", "true_upsell",
                   "complete_the_look", "cart_nudge"
    product_ids: list of product-ids involved (will be stored as JSON)
    metadata: any extra structured info (e.g. bandit_applied, confidence)
    """
    conn = get_connection()
    conn.execute(
        "INSERT INTO decisions (timestamp, session_id, decision_type, product_ids, reasoning, metadata) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (
            datetime.now(timezone.utc).isoformat(),
            session_id,
            decision_type,
            json.dumps(product_ids),
            reasoning,
            json.dumps(metadata or {}),
        ),
    )
    conn.commit()
    conn.close()


def log_transaction(session_id, status, order_total, razorpay_order_id, item_ids, metadata=None):
    """Records the final outcome of a purchase attempt."""
    conn = get_connection()
    conn.execute(
        "INSERT INTO transactions (timestamp, session_id, status, order_total, razorpay_order_id, item_ids, metadata) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            datetime.now(timezone.utc).isoformat(),
            session_id,
            status,
            order_total,
            razorpay_order_id,
            json.dumps(item_ids),
            json.dumps(metadata or {}),
        ),
    )
    conn.commit()
    conn.close()


def get_session_history(session_id):
    """Fetches all decisions + the transaction for a given session, in order."""
    conn = get_connection()
    decisions = conn.execute(
        "SELECT * FROM decisions WHERE session_id = ? ORDER BY timestamp", (session_id,)
    ).fetchall()
    transactions = conn.execute(
        "SELECT * FROM transactions WHERE session_id = ? ORDER BY timestamp", (session_id,)
    ).fetchall()
    conn.close()
    return {
        "decisions": [dict(row) for row in decisions],
        "transactions": [dict(row) for row in transactions],
    }


def get_recent_activity(limit=20):
    """Fetches the most recent decisions across ALL sessions — this is
    what the Phase 10 dashboard will show as a live feed."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM decisions ORDER BY timestamp DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


if __name__ == "__main__":
    init_db()
    print(f"Audit database initialized at: {DB_PATH}")

    # Quick smoke-test: log a fake decision and transaction, then read them back.
    test_session = "test_session_001"
    log_decision(
        session_id=test_session,
        decision_type="main_selection",
        product_ids=["M0244"],
        reasoning="Test reasoning: this is a formal shirt matching the request.",
        metadata={"confidence": "high", "bandit_applied": False},
    )
    log_transaction(
        session_id=test_session,
        status="auto_approved",
        order_total=692,
        razorpay_order_id="order_test123",
        item_ids=["M0244"],
    )

    print("\nSession history for test_session_001:")
    history = get_session_history(test_session)
    print(json.dumps(history, indent=2))

    print("\nRecent activity (all sessions):")
    recent = get_recent_activity(limit=5)
    print(json.dumps(recent, indent=2))