"""
Phase 4 - Policy Engine: orchestrates the full buyer-agent pipeline
(product selection -> upsell/cross-sell -> approval-gate check) according
to the customer's chosen mode and stated budgets.

Phase 6 addition: bandit-based product-selection refinement, with
reward-feedback wired here.

Phase 7 addition: every decision and the final transaction outcome are
logged to the SQLite audit trail, keyed by a per-purchase session_id.

Phase 8 addition: after every successful (auto_approved) transaction, the
merchant-side agent automatically re-evaluates demand and updates its
promotions — this closes the multi-agent loop autonomously, without a
human needing to manually re-run the merchant-agent script.
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
        but don't finalize anything. No budget enforcement here — the
        human sees real prices and decides for themselves.
        """
        from similar_items import decide_similar_items
        from upsell_true import decide_upsell_upgrade

        upsell_result = decide_upsell_upgrade(main_product, self.all_products)
        complete_look_result = decide_complete_the_look(main_product, self.products_by_id)
        similar_result = decide_similar_items(main_product, self.all_products)

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
            "complete_the_look_options": complete_look_result,
            "similar_items_options": similar_result,
        }

    def _build_autonomous_order(self, main_product, main_decision, addons_opted_in, addons_budget, session_id):
        """
        Fully-Autonomous mode: the engine decides everything itself,
        bounded by the customer's own stated budgets, then checks the
        final total against the merchant-side approval-gate. Every
        sub-decision and the final transaction outcome are logged, and a
        successful order triggers the merchant-agent's demand re-evaluation.
        """
        order_items = [main_product]
        decision_log = [{
            "item": main_product["id"],
            "action": "main_selection",
            "reasoning": main_decision["reasoning"],
        }]

        # --- True Upsell: bounded by the CUSTOMER's own primary price
        # ceiling, not an internal multiplier.
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

        # --- Approval gate: merchant-side bound, applies to the FINAL
        # order total regardless of how it was assembled.
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

            # Feed the outcome back to the bandit.
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

        # Log the final transaction outcome regardless of status.
        log_transaction(
            session_id=session_id,
            status=status,
            order_total=order_total,
            razorpay_order_id=razorpay_order_id,
            item_ids=[p["id"] for p in order_items],
            metadata={"approval_threshold": approval_threshold},
        )

        # After every successful transaction, let the merchant-agent
        # re-evaluate demand and update its promotions — this closes the
        # loop so the two agents interact autonomously, without needing
        # a human to manually re-run the merchant-agent script.
        if status == "auto_approved":
            merchant_result = run_merchant_agent(session_id=session_id)
            result["merchant_agent_promotions"] = merchant_result

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
    print(f"Session ID: {result['session_id']}")
    print(f"Status: {result['status']}")
    print(f"Order total: ₹{result.get('order_total')}")
    print(f"Merchant-agent promotions after this order: {result.get('merchant_agent_promotions', 'N/A (not auto_approved)')}")

    print("\n" + "=" * 60)
    print("Full audit trail for this session:")
    sys.path.append(str(Path(__file__).parent.parent / "audit-service"))
    from audit_db import get_session_history

    history = get_session_history(result["session_id"])
    print(json.dumps(history, indent=2))