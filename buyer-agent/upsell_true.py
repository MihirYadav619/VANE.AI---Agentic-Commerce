# ============================================================
# upsell_true.py
# ============================================================
"""
Phase 3 - Step 2a: True upsell reasoning.

Given an already-selected product, checks whether a genuinely better
(same category, higher price, meaningfully higher rating) alternative
exists — and if so, asks the LLM to judge whether suggesting an upgrade
is worthwhile. This is distinct from "Complete the Look" (which suggests
DIFFERENT-category complementary items) — this only ever suggests a
same-category replacement for the item the customer already chose.
"""

import json
import os
import time
from pathlib import Path

from dotenv import load_dotenv

ENV_PATH = Path(__file__).parent.parent / "backend" / ".env"
load_dotenv(dotenv_path=ENV_PATH)

from groq import Groq, BadRequestError

MODEL_NAME = "openai/gpt-oss-20b"
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
                print(f"[upsell_true] Tool-call JSON parse failed, retrying (attempt {attempt + 1})...")
                time.sleep(0.5)
                continue
            raise


# Sanity-check cap: an upgrade suggestion is only ever reasonable up to this
# multiple of the original item's price. This exists purely to block absurd
# jumps (e.g. suggesting a ₹17,000 "upgrade" for a ₹399 item) — it is NOT
# meant to be a tight budget rule the way Complete-the-Look's is, since a
# genuine upgrade naturally costs more than the original.
MAX_UPGRADE_PRICE_MULTIPLIER = 3.0

# How many higher-priced, higher-rated same-category candidates to show the LLM.
NUM_UPGRADE_CANDIDATES = 5


def find_upgrade_candidates(main_product, all_products):
    """
    Filters the full catalog down to a short list of plausible upgrade
    candidates: same category, priced higher, in stock, and with a rating
    at or above the main product's rating (an upgrade with a WORSE rating
    makes no sense to suggest).

    Sorted by rating (best first), so the LLM sees the most genuinely
    "better" options first.
    """
    same_category = [
        p for p in all_products
        if p["category"] == main_product["category"]
        and p["id"] != main_product["id"]
        and p["price"] > main_product["price"]
        and p["price"] <= main_product["price"] * MAX_UPGRADE_PRICE_MULTIPLIER
        and p["stock"] > 0
        and p["rating"] >= main_product["rating"]
    ]
    same_category.sort(key=lambda p: (-p["rating"], p["price"]))
    return same_category[:NUM_UPGRADE_CANDIDATES]


UPGRADE_TOOL = {
    "type": "function",
    "function": {
        "name": "record_upgrade_decision",
        "description": "Records whether to suggest a same-category premium upgrade.",
        "parameters": {
            "type": "object",
            "properties": {
                "should_suggest": {
                    "type": "boolean",
                    "description": "True if a genuinely worthwhile upgrade exists among the candidates."
                },
                "suggested_product_id": {
                    "type": ["string", "null"],
                    "description": "The id of the best upgrade candidate, or null if should_suggest is false."
                },
                "reasoning": {
                    "type": "string",
                    "description": "Clear explanation of why this upgrade is (or isn't) worth suggesting, for the audit trail."
                }
            },
            "required": ["should_suggest", "suggested_product_id", "reasoning"]
        }
    }
}

UPGRADE_SYSTEM_PROMPT = """You are a shopping assistant deciding whether to \
suggest a PREMIUM UPGRADE — a higher-priced alternative in the exact same \
product category as something the customer already chose to buy.

You will be given the customer's selected product and a list of candidate \
upgrades (same category, higher price, rating at or above the original).

Rules you must follow:
1. Only suggest an upgrade if it offers genuine, meaningfully better value —
   a notably higher rating, or clearly better-sounding attributes in its
   description (e.g. better material, better brand reputation). A tiny
   rating difference (e.g. 4.2 vs 4.3) combined with a large price jump is
   NOT worth suggesting.
2. The price increase should feel proportionate to the improvement. A small
   price increase for a meaningfully better product is a good suggestion;
   a huge price increase for a marginal improvement is not.
3. If no candidate offers a genuinely compelling upgrade, set should_suggest
   to false. Do not force an upgrade suggestion just because candidates exist.
4. Keep your reasoning concise (1-2 sentences).
5. Use plain ASCII punctuation only in your reasoning — regular hyphens (-)
   and straight quotes ('  "), never typographic dashes, curly/smart quotes,
   or other special Unicode punctuation. This keeps your output valid,
   parseable JSON.
6. You must call the record_upgrade_decision tool exactly once."""


def decide_upsell_upgrade(main_product, all_products):
    """
    main_product: the full product dict already selected as the purchase
                  (from reasoning_engine.py's decide())
    all_products: the full catalog list (list of product dicts)
    """
    candidates = find_upgrade_candidates(main_product, all_products)

    if not candidates:
        return {
            "should_suggest": False,
            "suggested_product_id": None,
            "reasoning": "No same-category product offers a rating-equal-or-better upgrade within a reasonable price range.",
        }

    candidate_lines = "\n".join(
        f"- id: {c['id']} | {c['name']} | price: ₹{c['price']} | rating: {c['rating']}"
        for c in candidates
    )

    user_message = (
        f"Customer selected: {main_product['name']} "
        f"(price: ₹{main_product['price']}, rating: {main_product['rating']})\n\n"
        f"Candidate upgrades (same category, priced higher):\n{candidate_lines}\n\n"
        f"Decide whether any of these is a genuinely worthwhile upgrade to suggest. "
        f"Use plain ASCII punctuation only."
    )

    response = call_llm_with_retry(
        model=MODEL_NAME,
        messages=[
            {"role": "system", "content": UPGRADE_SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
        tools=[UPGRADE_TOOL],
        tool_choice="required",
        temperature=0.3,
        max_tokens=1200,
    )

    tool_call = response.choices[0].message.tool_calls[0]
    decision = json.loads(tool_call.function.arguments)

    # Code-level safety net (same principle as upsell_engine.py): don't
    # fully trust the LLM's arithmetic/selection — verify the suggested
    # product actually exists among our pre-filtered candidates before
    # accepting the decision.
    if decision["should_suggest"]:
        valid_ids = {c["id"] for c in candidates}
        if decision["suggested_product_id"] not in valid_ids:
            decision["should_suggest"] = False
            decision["suggested_product_id"] = None
            decision["reasoning"] += " (Overridden by code-level safety check: suggested id was not among valid candidates.)"

    return decision


if __name__ == "__main__":
    import random

    CATALOG_PATH = Path(__file__).parent.parent / "backend" / "data" / "catalog.json"
    with open(CATALOG_PATH, "r", encoding="utf-8") as f:
        catalog = json.load(f)
    all_products = catalog["products"]

    # Bulk test: sample 25 random in-stock products and check upgrade-suggestion rate.
    random.seed(2)
    in_stock_products = [p for p in all_products if p["stock"] > 0]
    sample = random.sample(in_stock_products, min(25, len(in_stock_products)))

    successes = 0
    for main in sample:
        result = decide_upsell_upgrade(main, all_products)
        status = "✅ UPGRADE SUGGESTED" if result["should_suggest"] else "❌ no upgrade"
        print(f"{status} | {main['name'][:45]} (₹{main['price']}, {main['rating']}) -> {result.get('suggested_product_id')}")
        if result["should_suggest"]:
            successes += 1

    print(f"\nSuccess rate: {successes}/{len(sample)}")