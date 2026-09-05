# ============================================================
# reasoning_engine.py
# ============================================================
"""
Phase 3 - Step 1 (revised for Phase 6/7): Core buyer-agent reasoning with
LinUCB bandit refinement and merchant-agent promotion-awareness.

Takes a natural-language user request, retrieves candidates via hybrid
search (Phase 2), and asks an LLM to judge which candidate(s) genuinely
match the user's intent — with an explicit, honest "no good match" path
instead of always forcing a pick.

Phase 6 addition: once the LLM identifies a genuine match, if there are
OTHER candidates in the same category that are equally valid options, a
LinUCB bandit refines the final pick — but ONLY once that category has
accumulated enough real purchase-history to have a genuinely learned
preference, rather than a cold-start exploration artifact.

Phase 7 addition: before reasoning, the buyer-agent checks whether the
independent merchant-side agent has published any active promotions
relevant to the candidate categories — this is the multi-agent
interaction point: two separately-decision-making agents, communicating
through a shared, auditable signal (not a hardcoded coupling).
"""

import json
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

ENV_PATH = Path(__file__).parent.parent / "backend" / ".env"
load_dotenv(dotenv_path=ENV_PATH)

from groq import Groq, BadRequestError

sys.path.append(str(Path(__file__).parent.parent / "catalog-service"))
sys.path.append(str(Path(__file__).parent))
sys.path.append(str(Path(__file__).parent.parent / "merchant-agent"))
from hybrid_search import HybridSearch
from bandit import LinUCBBandit
from merchant_agent import get_active_promotions

MODEL_NAME = "openai/gpt-oss-120b"
NUM_CANDIDATES_TO_SHOW_LLM = 8

client = Groq(api_key=os.environ["GROQ_API_KEY"])


def call_llm_with_retry(max_retries=2, **kwargs):
    """
    Wraps client.chat.completions.create() with a retry for the
    occasional "tool_use_failed" / malformed-JSON error some models
    (notably GPT-OSS) can produce on longer reasoning fields. A small
    non-zero temperature (set by the caller) matters here: at
    temperature=0 the model can regenerate the EXACT same broken output
    on every retry, since there's no randomness to produce a different
    (hopefully valid) generation the second time around.
    """
    for attempt in range(max_retries + 1):
        try:
            return client.chat.completions.create(**kwargs)
        except BadRequestError as e:
            is_json_failure = "tool_use_failed" in str(e) or "Failed to parse tool call arguments" in str(e)
            if is_json_failure and attempt < max_retries:
                print(f"[reasoning_engine] Tool-call JSON parse failed, retrying (attempt {attempt + 1})...")
                time.sleep(0.5)
                continue
            raise


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
                    "description": "A clear, human-readable explanation of why this product was chosen (or why none matched). Mention any active merchant promotion relevant to the chosen product. This will be shown in the audit trail."
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

You may also be shown active merchant promotions for some categories —
these come from an independent merchant-side agent's own demand-analysis,
not from you. If a promotion applies to the category of the candidate you
select, mention it naturally in your reasoning (e.g. "this category
currently has a merchant-offered discount"). Do not let a promotion cause
you to pick a worse-matching candidate just because its category has a
discount — the match-quality judgment below still comes first.

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
5. Use plain ASCII punctuation only in your reasoning — regular hyphens (-) \
   and straight quotes ('  "), never typographic dashes, curly/smart quotes, \
   or other special Unicode punctuation. This keeps your output valid, \
   parseable JSON.
6. You must call the record_decision tool exactly once with your answer."""


class BuyerAgent:
    def __init__(self):
        print("Initializing buyer agent (loading search engine)...")
        self.search_engine = HybridSearch()
        self.bandit = LinUCBBandit()
        print("Buyer agent ready.")

    def decide(self, user_query):
        """
        Runs the full reasoning step: search -> promotion-check ->
        LLM judgment -> bandit refinement (only if the category has
        enough history) -> structured decision.
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

        # Check if the merchant-agent has an active promotion for any
        # category among these candidates — this is the buyer-agent
        # "listening" to the merchant-agent's independent decision,
        # via a shared file, not a hardcoded coupling between the two.
        active_promotions = get_active_promotions()
        candidate_categories = {c["category"] for c in candidates}
        relevant_promotions = {
            cat: details for cat, details in active_promotions.items()
            if cat in candidate_categories
        }

        candidate_text = build_candidate_summary(candidates)

        promotion_note = ""
        if relevant_promotions:
            promo_lines = "\n".join(
                f"- {cat}: {details['discount_percentage']}% off (merchant-agent promotion: {details['reason']})"
                for cat, details in relevant_promotions.items()
            )
            promotion_note = f"\n\nActive merchant promotions relevant to these candidates:\n{promo_lines}"

        user_message = (
            f"User request: \"{user_query}\"\n\n"
            f"Candidate products (from catalog search):\n{candidate_text}"
            f"{promotion_note}\n\n"
            f"Decide which candidate (if any) genuinely matches the user's request. "
            f"If a promotion applies to the category of your chosen candidate, mention it in your reasoning. "
            f"Use plain ASCII punctuation only."
        )

        response = call_llm_with_retry(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            tools=[REASONING_TOOL],
            tool_choice="required",
            temperature=0.3,
            max_tokens=1500,
        )

        tool_call = response.choices[0].message.tool_calls[0]
        decision = json.loads(tool_call.function.arguments)
        decision["candidates_considered"] = [c["id"] for c in candidates]
        decision["active_promotions_seen"] = relevant_promotions

        if decision["match_found"]:
            selected = next(c for c in candidates if c["id"] == decision["selected_product_id"])
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