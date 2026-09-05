"""
Phase 4 - Policy Engine: orchestrates the full buyer-agent pipeline
(product selection -> upsell/cross-sell -> approval-gate check) according
to the customer's chosen mode and stated budgets.

Phase 6: bandit-based product-selection refinement, with reward-feedback
wired here.

Phase 7: every decision and the final transaction outcome are logged to
the SQLite audit trail, keyed by a per-purchase session_id.

Phase 8: after every successful (auto_approved) transaction, the
merchant-side agent automatically re-evaluates demand and updates its
promotions.

Phase 9: approve_pending_order() completes the loop for orders that were
flagged pending_approval by the gate.

Phase 10: finalize_selection() completes the loop for Human-Browse mode
single-search selections. checkout_cart() generalizes this further to
support a CART — an arbitrary list of products accumulated across
MULTIPLE separate searches, checked out together in one transaction.
"""

import json
import os
import sys
import uuid
from pathlib import Path

sys.path.append(str(Path(__file__).parent))
sys.path.append(str(Path(__file__).parent.parent / "catalog-service"))
sys.path.append(str(Path(__file__).parent.parent / "audit-service"))
sys.path.append(str(Path(__file__).parent.parent / "merchant-agent"))

from reasoning_engine import BuyerAgent
from upsell_true import find_upgrade_candidates
from complete_the_look import decide_complete_the_look
from razorpay_client import create_order
from audit_db import init_db, log_decision, log_transaction
from merchant_agent import run_merchant_agent

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
    merchant-side approval-gate. Every decision step is logged to the
    audit trail, and a successful order triggers the merchant-agent's
    own independent decision-cycle.
    """

    def __init__(self):
        print("Initializing policy engine (loading agent + catalog)...")
        self.buyer_agent = BuyerAgent()
        self.all_products = load_catalog()
        self.products_by_id = {p["id"]: p for p in self.all_products}
        self.policy = load_policy()
        init_db()
        print("Policy engine ready.")

    def build_order(self, query, mode="browse", addons_opted_in=False, addons_budget=0):
        """
        Runs the full pipeline and returns a structured order-decision.
        Every call gets its own session_id, used to group all logged
        decisions + the final transaction in the audit trail.
        """
        if mode not in ("autonomous", "browse"):
            raise ValueError(f"Invalid mode: {mode}. Must be 'autonomous' or 'browse'.")

        session_id = f"session_{uuid.uuid4().hex[:12]}"

        main_decision = self.buyer_agent.decide(query)

        log_decision(
            session_id=session_id,
            decision_type="main_selection",
            product_ids=[main_decision["selected_product_id"]] if main_decision["match_found"] else [],
            reasoning=main_decision["reasoning"],
            metadata={
                "confidence": main_decision.get("confidence"),
                "bandit_applied": main_decision.get("bandit_applied", False),
                "bandit_status": main_decision.get("bandit_status"),
                "match_found": main_decision["match_found"],
                "active_promotions_seen": main_decision.get("active_promotions_seen", {}),
            },
        )

        if not main_decision["match_found"]:
            return {
                "status": "no_match",
                "reasoning": main_decision["reasoning"],
                "order": None,
                "session_id": session_id,
            }

        main_product = self.products_by_id[main_decision["selected_product_id"]]

        if mode == "browse":
            result = self._build_browse_options(main_product, main_decision, session_id)
        else:
            result = self._build_autonomous_order(
                main_product, main_decision, addons_opted_in, addons_budget, session_id
            )

        result["session_id"] = session_id
        return result

    def _build_browse_options(self, main_product, main_decision, session_id):
        """
        Human-Browse mode: gather everything the customer COULD choose,
        but don't finalize anything. Full product details (not just IDs)
        are attached so the frontend can render everything directly.
        """
        from similar_items import decide_similar_items
        from upsell_true import decide_upsell_upgrade

        upsell_result = decide_upsell_upgrade(main_product, self.all_products)
        complete_look_result = decide_complete_the_look(main_product, self.products_by_id)
        similar_result = decide_similar_items(main_product, self.all_products)

        upsell_product = None
        if upsell_result.get("should_suggest") and upsell_result.get("suggested_product_id"):
            upsell_product = self.products_by_id.get(upsell_result["suggested_product_id"])

        complete_look_products = [
            self.products_by_id[pid] for pid in complete_look_result["suggested_product_ids"]
            if pid in self.products_by_id
        ]
        similar_products = [
            self.products_by_id[pid] for pid in similar_result["suggested_product_ids"]
            if pid in self.products_by_id
        ]

        log_decision(
            session_id=session_id,
            decision_type="browse_options_generated",
            product_ids=(
                [upsell_result.get("suggested_product_id")] if upsell_result.get("should_suggest") else []
            ) + complete_look_result["suggested_product_ids"] + similar_result["suggested_product_ids"],
            reasoning="Options surfaced for human selection (browse mode) — not finalized.",
            metadata={"mode": "browse"},
        )

        return {
            "status": "awaiting_human_selection",
            "main_product": main_product,
            "main_product_reasoning": main_decision["reasoning"],
            "upsell_option": upsell_result,
            "upsell_product": upsell_product,
            "complete_the_look_options": complete_look_result,
            "complete_the_look_products": complete_look_products,
            "similar_items_options": similar_result,
            "similar_items_products": similar_products,
        }

    def _build_autonomous_order(self, main_product, main_decision, addons_opted_in, addons_budget, session_id):
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

        primary_budget_ceiling = main_product["price"]
        upgrade_candidates = find_upgrade_candidates(main_product, self.all_products)
        upgrade_candidates = [c for c in upgrade_candidates if c["price"] <= primary_budget_ceiling]

        final_product = main_product
        if upgrade_candidates:
            upsell_result = self._decide_upgrade_from_candidates(main_product, upgrade_candidates)
            if upsell_result["should_suggest"]:
                final_product = self.products_by_id[upsell_result["suggested_product_id"]]
                order_items = [final_product]
                decision_log.append({
                    "item": final_product["id"],
                    "action": "true_upsell_applied",
                    "reasoning": upsell_result["reasoning"],
                })
                log_decision(
                    session_id=session_id,
                    decision_type="true_upsell",
                    product_ids=[final_product["id"]],
                    reasoning=upsell_result["reasoning"],
                )

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

            order_items.extend(accepted_addons)
            decision_log.append({
                "items": [p["id"] for p in accepted_addons],
                "action": "complete_the_look_applied",
                "reasoning": complete_look_result["reasoning"],
                "addons_budget": addons_budget,
                "addons_spent": running_total,
            })
            log_decision(
                session_id=session_id,
                decision_type="complete_the_look",
                product_ids=[p["id"] for p in accepted_addons],
                reasoning=complete_look_result["reasoning"],
                metadata={"addons_budget": addons_budget, "addons_spent": running_total},
            )

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

        razorpay_order_id = None
        if status == "auto_approved":
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
            razorpay_order_id = razorpay_order["id"]

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

        log_transaction(
            session_id=session_id,
            status=status,
            order_total=order_total,
            razorpay_order_id=razorpay_order_id,
            item_ids=[p["id"] for p in order_items],
            metadata={"approval_threshold": approval_threshold},
        )

        if status == "auto_approved":
            merchant_result = run_merchant_agent(session_id=session_id)
            result["merchant_agent_promotions"] = merchant_result

        return result

    def approve_pending_order(self, order_items, order_total, session_id):
        """
        Called after a human (merchant/customer) approves an order that
        was previously flagged pending_approval by the approval-gate.
        """
        razorpay_order = create_order(
            amount_rupees=order_total,
            receipt_id=f"order_{uuid.uuid4().hex[:10]}",
            notes={
                "item_ids": ",".join(p["id"] for p in order_items),
                "approval_type": "human_approved_after_gate",
            },
        )

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

        log_decision(
            session_id=session_id,
            decision_type="human_approval",
            product_ids=[p["id"] for p in order_items],
            reasoning=f"Order for ₹{order_total} manually approved after exceeding the auto-approval threshold.",
        )
        log_transaction(
            session_id=session_id,
            status="approved_and_completed",
            order_total=order_total,
            razorpay_order_id=razorpay_order["id"],
            item_ids=[p["id"] for p in order_items],
        )

        merchant_result = run_merchant_agent(session_id=session_id)

        return {
            "status": "approved_and_completed",
            "razorpay_order_id": razorpay_order["id"],
            "razorpay_key_id": os.environ["RAZORPAY_KEY_ID"],
            "merchant_agent_promotions": merchant_result,
        }

    def finalize_selection(self, main_product_id, addon_ids, session_id):
        """
        Called when a customer in Human-Browse mode has finished manually
        selecting items from a SINGLE search (a main product + any chosen
        add-ons/similar-items). Kept for backward compatibility / simple
        single-search checkouts — checkout_cart() below is the more
        general version used for multi-search carts.
        """
        main_product = self.products_by_id[main_product_id]
        addon_products = [self.products_by_id[pid] for pid in addon_ids if pid in self.products_by_id]
        order_items = [main_product] + addon_products
        return self._checkout_items(order_items, session_id, decision_type="human_selection_finalized")

    def checkout_cart(self, product_ids, session_id):
        """
        Checks out an arbitrary list of products accumulated across
        potentially MULTIPLE separate searches (Browse mode's cart) —
        unlike finalize_selection(), which is scoped to one search's
        main-item + its suggested add-ons, this accepts any product-id
        list the customer built up over time by clicking "Add to Cart"
        on different, possibly-unrelated searches.
        """
        order_items = [self.products_by_id[pid] for pid in product_ids if pid in self.products_by_id]

        if not order_items:
            return {"status": "error", "reasoning": "Cart is empty or contains invalid product ids."}

        return self._checkout_items(order_items, session_id, decision_type="cart_checkout")

    def _checkout_items(self, order_items, session_id, decision_type):
        """
        Shared checkout logic used by both finalize_selection() and
        checkout_cart(): compute total, check the approval-gate, create
        the Razorpay order if auto-approved, feed the bandit for every
        distinct category represented, log everything, and trigger the
        merchant-agent.
        """
        order_total = sum(p["price"] for p in order_items)
        approval_threshold = self.policy["approval_gate"]["approval_required_above"]
        status = "pending_approval" if order_total > approval_threshold else "auto_approved"

        log_decision(
            session_id=session_id,
            decision_type=decision_type,
            product_ids=[p["id"] for p in order_items],
            reasoning=f"Customer manually selected/checked-out {len(order_items)} item(s).",
        )

        if status == "auto_approved":
            razorpay_order = create_order(
                amount_rupees=order_total,
                receipt_id=f"order_{uuid.uuid4().hex[:10]}",
                notes={
                    "item_ids": ",".join(p["id"] for p in order_items),
                    "mode": decision_type,
                },
            )

            categories_seen = set()
            for item in order_items:
                if item["category"] in categories_seen:
                    continue
                categories_seen.add(item["category"])
                same_category_products = [
                    p for p in self.all_products if p["category"] == item["category"]
                ]
                if len(same_category_products) > 1:
                    self.buyer_agent.bandit.update(
                        chosen_product=item,
                        all_candidates=same_category_products,
                        category=item["category"],
                        reward=1.0,
                    )

            log_transaction(
                session_id=session_id,
                status=status,
                order_total=order_total,
                razorpay_order_id=razorpay_order["id"],
                item_ids=[p["id"] for p in order_items],
            )
            merchant_result = run_merchant_agent(session_id=session_id)

            return {
                "status": status,
                "order_items": order_items,
                "order_total": order_total,
                "razorpay_order_id": razorpay_order["id"],
                "razorpay_key_id": os.environ["RAZORPAY_KEY_ID"],
                "session_id": session_id,
                "merchant_agent_promotions": merchant_result,
            }
        else:
            log_transaction(
                session_id=session_id,
                status=status,
                order_total=order_total,
                razorpay_order_id=None,
                item_ids=[p["id"] for p in order_items],
            )
            return {
                "status": status,
                "order_items": order_items,
                "order_total": order_total,
                "approval_threshold": approval_threshold,
                "session_id": session_id,
            }

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

        response = ut.call_llm_with_retry(
            model=ut.MODEL_NAME,
            messages=[
                {"role": "system", "content": ut.UPGRADE_SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            tools=[ut.UPGRADE_TOOL],
            tool_choice="required",
            temperature=0.3,
            max_tokens=1200,
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
    print("TEST: Cart checkout with multiple unrelated items")
    result = engine.checkout_cart(
        product_ids=["M0244", "M0401"],
        session_id=f"cart_test_{uuid.uuid4().hex[:8]}",
    )
    print(f"Status: {result['status']}")
    print(f"Order total: ₹{result['order_total']}")
    print(f"Items: {[item['name'] for item in result['order_items']]}")