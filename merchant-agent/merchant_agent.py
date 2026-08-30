"""
Phase 7/8 - Merchant-Side Agent: monitors demand signals from the audit
trail and autonomously decides bounded promotions.

This is the SECOND agent in the system — distinct from the buyer-agent,
it thinks from the MERCHANT's side: "which categories are trending, and
should I offer a temporary bounded discount to capture more demand?"

Communication with the buyer-agent happens through a shared JSON file
(active_promotions.json) — deliberately simple for this scope, rather
than a complex message-passing protocol. Its own decisions are ALSO
logged to the same audit trail the buyer-agent uses, so the complete
multi-agent system is auditable, not just the buyer's half.
"""

import json
import sys
from pathlib import Path
from collections import Counter

sys.path.append(str(Path(__file__).parent.parent / "audit-service"))
from audit_db import get_connection, log_decision

PROMOTIONS_PATH = Path(__file__).parent.parent / "backend" / "data" / "active_promotions.json"

# Bounded rules — the merchant-agent can NEVER exceed these, no matter
# what the demand-signal looks like. This keeps it "agentic" (it decides
# WHEN and WHETHER to apply a promotion) while still "bounded" (it can
# never invent an unbounded discount).
MAX_DISCOUNT_PERCENTAGE = 10
DEMAND_WINDOW_SIZE = 20  # look at the last N auto_approved transactions
DEMAND_THRESHOLD_COUNT = 3  # a category needs at least this many purchases in the window to be "trending"


def get_recent_category_demand():
    """
    Looks at the last DEMAND_WINDOW_SIZE successful transactions and
    counts how many purchases fell into each product category — this is
    the merchant-agent's "demand signal", built directly from the same
    audit trail the buyer-agent's decisions are already logged into.
    """
    conn = get_connection()
    rows = conn.execute(
        "SELECT item_ids FROM transactions WHERE status = 'auto_approved' "
        "ORDER BY timestamp DESC LIMIT ?",
        (DEMAND_WINDOW_SIZE,),
    ).fetchall()
    conn.close()

    catalog_path = Path(__file__).parent.parent / "backend" / "data" / "catalog.json"
    with open(catalog_path, "r", encoding="utf-8") as f:
        products_by_id = {p["id"]: p for p in json.load(f)["products"]}

    category_counts = Counter()
    for row in rows:
        item_ids = json.loads(row["item_ids"])
        for pid in item_ids:
            product = products_by_id.get(pid)
            if product:
                category_counts[product["category"]] += 1

    return category_counts


def decide_promotions():
    """
    The merchant-agent's core decision: for each category trending above
    DEMAND_THRESHOLD_COUNT in the recent window, decide a bounded discount.

    This is intentionally rule-based (not LLM-based) — the decision here
    is a simple, deterministic business-rule ("if demand > threshold,
    apply capped discount"), which is easier to defend as genuinely
    "bounded" than an LLM freely deciding discount percentages.
    """
    demand = get_recent_category_demand()
    promotions = {}

    for category, count in demand.items():
        if count >= DEMAND_THRESHOLD_COUNT:
            discount = min(MAX_DISCOUNT_PERCENTAGE, 2 * (count - DEMAND_THRESHOLD_COUNT + 1))
            promotions[category] = {
                "discount_percentage": discount,
                "reason": f"{count} purchases in the last {DEMAND_WINDOW_SIZE} transactions (trending demand).",
            }

    return promotions


def publish_promotions(promotions):
    """Writes the decided promotions to a shared file the buyer-agent reads from."""
    PROMOTIONS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(PROMOTIONS_PATH, "w", encoding="utf-8") as f:
        json.dump(promotions, f, indent=2)


def get_active_promotions():
    """Called by the BUYER-agent to check current merchant-side promotions."""
    if not PROMOTIONS_PATH.exists():
        return {}
    with open(PROMOTIONS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def run_merchant_agent(session_id="merchant_agent_cycle"):
    """
    One "tick" of the merchant-agent's decision cycle. Logs its own
    decisions to the shared audit trail (decision_type="merchant_promotion")
    whenever a category's promotion actually CHANGES, so the complete
    multi-agent interaction is traceable in one place.
    """
    previous_promotions = get_active_promotions()
    new_promotions = decide_promotions()

    changed_categories = {
        cat for cat in set(previous_promotions) | set(new_promotions)
        if previous_promotions.get(cat) != new_promotions.get(cat)
    }

    for category in changed_categories:
        old = previous_promotions.get(category)
        new = new_promotions.get(category)
        if new is None:
            reasoning = f"Promotion removed for {category} — demand no longer meets the trending threshold."
        elif old is None:
            reasoning = f"New promotion decided for {category}: {new['discount_percentage']}% off. {new['reason']}"
        else:
            reasoning = f"Promotion updated for {category}: {old['discount_percentage']}% -> {new['discount_percentage']}%. {new['reason']}"

        log_decision(
            session_id=session_id,
            decision_type="merchant_promotion",
            product_ids=[],
            reasoning=reasoning,
            metadata={"category": category, "promotion": new},
        )

    publish_promotions(new_promotions)
    return new_promotions


if __name__ == "__main__":
    print("Merchant agent: analyzing recent demand...")
    result = run_merchant_agent()

    if result:
        print(f"Merchant agent: decided {len(result)} promotion(s):")
        for category, details in result.items():
            print(f"  {category}: {details['discount_percentage']}% off — {details['reason']}")
    else:
        print("Merchant agent: no category currently meets the trending-demand threshold.")

    print("\nVerifying: reading back published promotions...")
    active = get_active_promotions()
    print(json.dumps(active, indent=2))