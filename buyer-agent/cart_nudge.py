"""
Phase 3 - Step 3: Cart-value threshold nudge.

Unlike the other three revenue mechanisms (True Upsell, Complete-the-Look,
Similar Items), this one is pure arithmetic — no LLM call needed, since
"how far is the cart from a threshold" has no ambiguity to reason about.
Keeping this LLM-free makes it faster, free to run, and impossible to get
"wrong" in an unpredictable way.
"""

import json
from pathlib import Path

POLICY_PATH = Path(__file__).parent.parent / "backend" / "data" / "policy.json"


def load_policy():
    with open(POLICY_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def get_cart_nudge(cart_total):
    """
    Given a cart's current total, returns a nudge decision:
      - already_unlocked: True if the cart already meets the threshold
      - should_nudge: True if a nudge message should be shown (cart is
        below the threshold, but close enough that closing the gap feels
        realistic rather than an obviously-fake upsell push)
      - message: a ready-to-show string, or None if no nudge applies
      - gap_amount: how much more the customer needs to add (0 if unlocked)
    """
    policy = load_policy()
    incentives = policy.get("cart_incentives", {})
    threshold = incentives.get("free_delivery_threshold", 1999)
    max_gap_pct = incentives.get("nudge_trigger_max_gap_percentage", 30)

    if cart_total >= threshold:
        return {
            "already_unlocked": True,
            "should_nudge": False,
            "message": f"You've unlocked free delivery! (Cart total: ₹{cart_total})",
            "gap_amount": 0,
        }

    gap_amount = threshold - cart_total
    gap_percentage = (gap_amount / threshold) * 100

    if gap_percentage <= max_gap_pct:
        return {
            "already_unlocked": False,
            "should_nudge": True,
            "message": f"Add ₹{gap_amount} more to unlock free delivery!",
            "gap_amount": gap_amount,
        }

    # Gap is too large to make the nudge feel realistic/relevant.
    return {
        "already_unlocked": False,
        "should_nudge": False,
        "message": None,
        "gap_amount": gap_amount,
    }


if __name__ == "__main__":
    test_cart_totals = [500, 1200, 1700, 1850, 1999, 2500]

    for total in test_cart_totals:
        result = get_cart_nudge(total)
        print(f"\nCart total: ₹{total}")
        print(f"  {result}")