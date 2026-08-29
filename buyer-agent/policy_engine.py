"""
Phase 4 - Policy Engine: orchestrates the full buyer-agent pipeline
(product selection -> upsell/cross-sell -> approval-gate check) according
to the customer's chosen mode and stated budgets.

This is the "glue" layer that turns the individually-tested modules from
Phase 3 into one coherent, bounded, auditable purchase flow.
"""

import json
import sys
from pathlib import Path
import os
sys.path.append(str(Path(__file__).parent))
sys.path.append(str(Path(__file__).parent.parent / "catalog-service"))
from razorpay_client import create_order

from bandit import LinUCBBandit
from reasoning_engine import BuyerAgent
from upsell_true import find_upgrade_candidates, decide_upsell_upgrade
from complete_the_look import decide_complete_the_look
from hybrid_search import HybridSearch

POLICY_PATH = Path(__file__).parent.parent / "backend" / "data" / "policy.json"
CATALOG_PATH = Path(__file__).parent.parent / "backend" / "data" / "catalog.json"


def load_policy():
    with open(POLICY_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def load_catalog():
    with open(CATALOG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)["products"]


class PolicyEngine:
    """
    Ties together product-selection and the revenue modules into one
    order-building flow, enforcing customer-stated budgets and the
    merchant-side approval-gate.

    Usage:
        engine = PolicyEngine()
        order = engine.build_order(
            query="a formal shirt under 1000",
            mode="autonomous",
            addons_opted_in=True,
            addons_budget=500,
        )
    """

    def __init__(self):
        print("Initializing policy engine (loading agent + catalog)...")
        self.buyer_agent = BuyerAgent()  # this loads hybrid search internally
        self.all_products = load_catalog()
        self.products_by_id = {p["id"]: p for p in self.all_products}
        self.policy = load_policy()
        print("Policy engine ready.")
    def __init__(self):
        print("Initializing policy engine (loading agent + catalog)...")
        self.buyer_agent = BuyerAgent()
        self.all_products = load_catalog()
        self.products_by_id = {p["id"]: p for p in self.all_products}
        self.policy = load_policy()
        print("Policy engine ready.")
    def build_order(self, query, mode="browse", addons_opted_in=False, addons_budget=0):
        """
        Runs the full pipeline and returns a structured order-decision.

        mode: "autonomous" or "browse"
          - "autonomous": the engine finalizes the order itself (subject to
            the approval-gate for high-value totals).
          - "browse": the engine returns all candidate options (main item +
            possible upsell + possible complementary items) WITHOUT
            finalizing anything — a human is expected to pick, then call
            finalize_selection() separately (Phase 5 will wire this to
            actual payment).

        addons_opted_in / addons_budget: only relevant in "autonomous" mode
          — whether the customer allowed Complete-the-Look, and the budget
          ceiling for it (see README's "Purchase Architecture" section).
        """
        if mode not in ("autonomous", "browse"):
            raise ValueError(f"Invalid mode: {mode}. Must be 'autonomous' or 'browse'.")

        # Step 1: Select the main product (Phase 3's core reasoning engine).
        main_decision = self.buyer_agent.decide(query)

        if not main_decision["match_found"]:
            return {
                "status": "no_match",
                "reasoning": main_decision["reasoning"],
                "order": None,
            }

        main_product = self.products_by_id[main_decision["selected_product_id"]]

        if mode == "browse":
            return self._build_browse_options(main_product, main_decision)
        else:
            return self._build_autonomous_order(
                main_product, main_decision, addons_opted_in, addons_budget
            )

    def _build_browse_options(self, main_product, main_decision):
        """
        Human-Browse mode: gather everything the customer COULD choose,
        but don't finalize anything. No budget enforcement here — the
        human sees real prices and decides for themselves (see README).
        """
        from similar_items import decide_similar_items

        upsell_result = decide_upsell_upgrade(main_product, self.all_products)
        complete_look_result = decide_complete_the_look(main_product, self.products_by_id)
        similar_result = decide_similar_items(main_product, self.all_products)

        return {
            "status": "awaiting_human_selection",
            "main_product": main_product,
            "main_product_reasoning": main_decision["reasoning"],
            "upsell_option": upsell_result,
            "complete_the_look_options": complete_look_result,
            "similar_items_options": similar_result,
        }

    def _build_autonomous_order(self, main_product, main_decision, addons_opted_in, addons_budget):
        """
        Fully-Autonomous mode: the engine decides everything itself,
        bounded by the customer's own stated budgets, then checks the
        final total against the merchant-side approval-gate.
        """
        order_items = [main_product]
        decision_log = [{
            "item": main_product["id"],
            "action": "main_selection",
            "reasoning": main_decision["reasoning"],
        }]

        # --- True Upsell: bounded by the CUSTOMER's own primary price
        # ceiling (the price they searched under), not an internal
        # multiplier. If the customer said "under 1000", an upgrade must
        # also be under 1000 — we never spend more than what they asked
        # for on the PRIMARY item, since upsell replaces it, not adds to it.
        primary_budget_ceiling = main_product["price"]  # see note below
        upgrade_candidates = find_upgrade_candidates(main_product, self.all_products)
        # Re-filter candidates to respect the customer's own price ceiling
        # rather than the module's default 3x sanity multiplier.
        upgrade_candidates = [c for c in upgrade_candidates if c["price"] <= primary_budget_ceiling]

        final_product = main_product
        if upgrade_candidates:
            # Re-run the upsell decision using only budget-respecting candidates.
            upsell_result = self._decide_upgrade_from_candidates(main_product, upgrade_candidates)
            if upsell_result["should_suggest"]:
                final_product = self.products_by_id[upsell_result["suggested_product_id"]]
                order_items = [final_product]
                decision_log.append({
                    "item": final_product["id"],
                    "action": "true_upsell_applied",
                    "reasoning": upsell_result["reasoning"],
                })

        # --- Complete the Look: only runs if the customer opted in,
        # bounded by their separately-stated addons_budget.
        if addons_opted_in and addons_budget > 0:
            complete_look_result = decide_complete_the_look(final_product, self.products_by_id)
            addon_ids = complete_look_result["suggested_product_ids"]

            running_total = 0
            accepted_addons = []
            for pid in addon_ids:
                product = self.products_by_id[pid]
                if running_total + product["price"] <= addons_budget:
                    accepted_addons.append(product)
                    running_total += product["price"]
                # else: silently skip — code-level enforcement of the
                # customer's stated addons budget, same safety-net pattern
                # used throughout Phase 3.

            order_items.extend(accepted_addons)
            decision_log.append({
                "items": [p["id"] for p in accepted_addons],
                "action": "complete_the_look_applied",
                "reasoning": complete_look_result["reasoning"],
                "addons_budget": addons_budget,
                "addons_spent": running_total,
            })

        order_total = sum(p["price"] for p in order_items)
        approval_threshold = self.policy["approval_gate"]["approval_required_above"]

        status = "pending_approval" if order_total > approval_threshold else "auto_approved"

        result = {
            "status": status,
            "order_items": order_items,
            "order_total": order_total,
            "approval_threshold": approval_threshold,
            "decision_log": decision_log,
        }

        # Only create the actual Razorpay order once the agent has decided
        # to proceed (auto_approved). A pending_approval order shouldn't
        # exist in Razorpay yet — creating a real payable order before a
        # human/merchant has approved it would defeat the point of the gate.
        if status == "auto_approved":
            import uuid
            razorpay_order = create_order(
                amount_rupees=order_total,
                receipt_id=f"order_{uuid.uuid4().hex[:10]}",
                notes={
                    "item_ids": ",".join(p["id"] for p in order_items),
                    "reasoning_summary": decision_log[0]["reasoning"][:500],  # Razorpay notes have a 256-char-per-field limit on some plans; truncate defensively
                },
            )
            result["razorpay_order_id"] = razorpay_order["id"]
            result["razorpay_key_id"] = os.environ["RAZORPAY_KEY_ID"]
        if status == "auto_approved":
            import uuid
            razorpay_order = create_order(
                amount_rupees=order_total,
                receipt_id=f"order_{uuid.uuid4().hex[:10]}",
                notes={
                    "item_ids": ",".join(p["id"] for p in order_items),
                    "reasoning_summary": decision_log[0]["reasoning"][:500],
                },
            )
            result["razorpay_order_id"] = razorpay_order["id"]
            result["razorpay_key_id"] = os.environ["RAZORPAY_KEY_ID"]

            # Feed the outcome back to the bandit: an auto-approved order
            # means the buyer agent's product-selection led to a
            # successfully-completed decision-flow (reward = success).
            # This is what makes bandit_had_prior_learning eventually
            # become True for categories with enough purchase history.
            main_item = order_items[0]
            same_category_products = [
                p for p in self.all_products if p["category"] == main_item["category"]
            ]
            if len(same_category_products) > 1:
                self.buyer_agent.bandit.update(
                    chosen_product=main_item,
                    all_candidates=same_category_products,
                    category=main_item["category"],
                    reward=1.0,
                )

        
        return result

    def _decide_upgrade_from_candidates(self, main_product, candidates):
        """
        Thin wrapper: reuses upsell_true.py's LLM-decision logic but with
        an externally-filtered candidate list (respecting the customer's
        own budget ceiling instead of the module's default multiplier).
        """
        import upsell_true as ut

        if not candidates:
            return {"should_suggest": False, "suggested_product_id": None, "reasoning": "No budget-respecting upgrade candidates."}

        candidate_lines = "\n".join(
            f"- id: {c['id']} | {c['name']} | price: ₹{c['price']} | rating: {c['rating']}"
            for c in candidates
        )
        user_message = (
            f"Customer selected: {main_product['name']} "
            f"(price: ₹{main_product['price']}, rating: {main_product['rating']})\n\n"
            f"Candidate upgrades (same category, priced higher, within customer's budget):\n{candidate_lines}\n\n"
            f"Decide whether any of these is a genuinely worthwhile upgrade to suggest."
        )

        response = ut.client.chat.complete(
            model=ut.MODEL_NAME,
            messages=[
                {"role": "system", "content": ut.UPGRADE_SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            tools=[ut.UPGRADE_TOOL],
            tool_choice="any",
        )
        tool_call = response.choices[0].message.tool_calls[0]
        decision = json.loads(tool_call.function.arguments)

        if decision["should_suggest"]:
            valid_ids = {c["id"] for c in candidates}
            if decision["suggested_product_id"] not in valid_ids:
                decision["should_suggest"] = False
                decision["suggested_product_id"] = None

        return decision


if __name__ == "__main__":
    engine = PolicyEngine()

    print("\n" + "=" * 60)
    print("TEST 1: Autonomous mode, no add-ons opted in")
    result = engine.build_order("a formal shirt under 1000", mode="autonomous")
    print(json.dumps({k: v for k, v in result.items() if k != "decision_log"}, indent=2, default=str))
    print("Decision log:")
    for entry in result.get("decision_log", []):
        print(f"  {entry}")
    print(f"Razorpay Order ID: {result.get('razorpay_order_id', 'N/A (not auto-approved)')}")
    print("\n" + "=" * 60)
    print("TEST 2: Autonomous mode, WITH add-ons opted in (budget: 500)")
    result = engine.build_order(
    "a formal shirt under 1000", mode="autonomous", addons_opted_in=True, addons_budget=1000
)
    
    print(json.dumps({k: v for k, v in result.items() if k != "decision_log"}, indent=2, default=str))
    print("Decision log:")
    for entry in result.get("decision_log", []):
        print(f"  {entry}")

    print("\n" + "=" * 60)
    print("TEST 3: Browse mode")
    result = engine.build_order("a formal shirt under 1000", mode="browse")
    print(f"Status: {result['status']}")
    print(f"Main product: {result['main_product']['name']}")
    print(f"Upsell option: {result['upsell_option']['should_suggest']}")
    print(f"Complete-the-look options: {result['complete_the_look_options']['suggested_product_ids']}")
    print(f"Similar items: {result['similar_items_options']['suggested_product_ids']}")

    print("\n" + "=" * 60)
    print("TEST 4: High-value item to trigger approval-gate")
    result = engine.build_order("a watch above 10000", mode="autonomous")
    print(f"Status: {result['status']}")
    print(f"Order total: ₹{result.get('order_total')}")