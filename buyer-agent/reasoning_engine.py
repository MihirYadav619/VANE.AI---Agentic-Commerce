"""
Phase 3 - Step 1 (revised for Phase 6): Core buyer-agent reasoning with
LinUCB bandit refinement.

Takes a natural-language user request, retrieves candidates via hybrid
search (Phase 2), and asks an LLM to judge which candidate(s) genuinely
match the user's intent — with an explicit, honest "no good match" path
instead of always forcing a pick.

Phase 6 addition: once the LLM identifies a genuine match, if there are
OTHER candidates in the same category that are equally valid options, a
LinUCB bandit refines the final pick — but ONLY once that category has
accumulated enough real purchase-history (see bandit.py's
has_sufficient_data()) to have a genuinely learned preference, rather
than a cold-start exploration artifact.
"""

import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

ENV_PATH = Path(__file__).parent.parent / "backend" / ".env"
load_dotenv(dotenv_path=ENV_PATH)

try:
    from mistralai.client import Mistral
except ImportError:
    from mistralai import Mistral

sys.path.append(str(Path(__file__).parent.parent / "catalog-service"))
sys.path.append(str(Path(__file__).parent))
from hybrid_search import HybridSearch
from bandit import LinUCBBandit

MODEL_NAME = "mistral-small-2603"
NUM_CANDIDATES_TO_SHOW_LLM = 8

client = Mistral(api_key=os.environ["MISTRAL_API_KEY"])


def build_candidate_summary(products):
    lines = []
    for p in products:
        lines.append(
            f"- id: {p['id']} | {p['name']} | category: {p['category']} | "
            f"price: ₹{p['price']} | rating: {p['rating']} | stock: {p['stock']}"
        )
    return "\n".join(lines)


REASONING_TOOL = {
    "type": "function",
    "function": {
        "name": "record_decision",
        "description": "Records the buyer agent's product-selection decision with reasoning.",
        "parameters": {
            "type": "object",
            "properties": {
                "match_found": {
                    "type": "boolean",
                    "description": "True if at least one candidate genuinely matches the user's intent."
                },
                "selected_product_id": {
                    "type": ["string", "null"],
                    "description": "The id of the best-matching product, or null if match_found is false."
                },
                "reasoning": {
                    "type": "string",
                    "description": "A clear, human-readable explanation of why this product was chosen (or why none matched). This will be shown in the audit trail."
                },
                "confidence": {
                    "type": "string",
                    "enum": ["high", "medium", "low"],
                    "description": "How confident the agent is that this is a genuinely good match for what the user asked for."
                }
            },
            "required": ["match_found", "selected_product_id", "reasoning", "confidence"]
        }
    }
}

SYSTEM_PROMPT = """You are a careful shopping assistant deciding which product \
(if any) from a short candidate list genuinely matches what the user asked for.

Important context: any price constraint in the user's request (e.g. "under \
5000") has ALREADY been enforced by the search system before you see this \
candidate list — every candidate shown to you already satisfies the price \
requirement. Do NOT re-check or re-calculate prices against the user's \
budget; take it as given that all candidates are within budget.

Rules you must follow:
1. Only consider constraints the user EXPLICITLY stated (category, explicit \
   color, explicit brand, explicit material). Do NOT invent additional \
   constraints the user didn't mention — for example, if the user asked for \
   "a formal shirt for office" without specifying gender, do not reject \
   women's items on the assumption that "office shirt" implies "men's shirt".
2. Distinguish between HARD constraints (explicitly stated, objective facts \
   like color or category) and SOFT preferences (subjective descriptors like \
   "comfortable", "stylish", "professional-looking"). Reject a candidate only \
   if it clearly violates a HARD constraint. Never reject a candidate solely \
   because a SOFT preference isn't explicitly confirmed in its description — \
   pick the best reasonable match instead and note the assumption.
3. If NONE of the candidates satisfy the explicitly stated HARD constraints, \
   set match_found to false and explain what was missing. It is better to \
   honestly say no good match exists than to force a bad recommendation — \
   but do not reject candidates over constraints the user never actually stated.
4. Keep your reasoning concise (1-3 sentences) and concrete.
5. You must call the record_decision tool exactly once with your answer."""


class BuyerAgent:
    def __init__(self):
        print("Initializing buyer agent (loading search engine)...")
        self.search_engine = HybridSearch()
        self.bandit = LinUCBBandit()
        print("Buyer agent ready.")

    def decide(self, user_query):
        """
        Runs the full reasoning step: search -> LLM judgment -> bandit
        refinement (only if the category has enough history) -> structured
        decision. Returns a dict with the decision details.
        """
        candidates = self.search_engine.search(user_query, top_k=NUM_CANDIDATES_TO_SHOW_LLM)

        if not candidates:
            return {
                "match_found": False,
                "selected_product_id": None,
                "reasoning": "No candidates were returned by search for this query.",
                "confidence": "high",
                "candidates_considered": [],
                "bandit_applied": False,
            }

        candidate_text = build_candidate_summary(candidates)

        user_message = (
            f"User request: \"{user_query}\"\n\n"
            f"Candidate products (from catalog search):\n{candidate_text}\n\n"
            f"Decide which candidate (if any) genuinely matches the user's request."
        )

        response = client.chat.complete(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            tools=[REASONING_TOOL],
            tool_choice="any",
        )

        tool_call = response.choices[0].message.tool_calls[0]
        decision = json.loads(tool_call.function.arguments)
        decision["candidates_considered"] = [c["id"] for c in candidates]

        if decision["match_found"]:
            selected = next(c for c in candidates if c["id"] == decision["selected_product_id"])

            # Find other candidates in the SAME category as the LLM's pick
            # — these are the genuinely-comparable options the bandit
            # should choose among.
            same_category_pool = [c for c in candidates if c["category"] == selected["category"]]

            if len(same_category_pool) > 1:
                has_enough_data = self.bandit.has_sufficient_data(selected["category"])

                if has_enough_data:
                    bandit_choice = self.bandit.select(same_category_pool, category=selected["category"])
                    if bandit_choice["id"] != selected["id"]:
                        decision["reasoning"] += (
                            f" (Bandit refined the final pick from {selected['id']} to "
                            f"{bandit_choice['id']} based on learned success patterns in this category.)"
                        )
                        decision["selected_product_id"] = bandit_choice["id"]
                    decision["bandit_applied"] = True
                else:
                    # Not enough real purchase history yet — trust the
                    # LLM's pick as-is. The bandit still silently observes
                    # this decision in the background (via update() after
                    # the outcome is known), but doesn't influence the
                    # choice until it has genuine signal to act on.
                    decision["bandit_applied"] = False
                    decision["bandit_status"] = "collecting_data_not_yet_overriding"

                decision["bandit_candidate_pool"] = [c["id"] for c in same_category_pool]
            else:
                decision["bandit_applied"] = False
        else:
            decision["bandit_applied"] = False

        return decision


if __name__ == "__main__":
    agent = BuyerAgent()

    test_queries = [
        "I need a formal shirt for office, comfortable fit",
        "blue denim jacket",
        "watch under 5000",
    ]

    for q in test_queries:
        print(f"\n{'='*60}\nUser: {q}")
        decision = agent.decide(q)
        print(json.dumps(decision, indent=2))