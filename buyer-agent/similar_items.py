# ============================================================
# similar_items.py
# ============================================================
"""
Phase 3 - Step 2c: "Similar Items" — same-category alternatives at a
comparable price point.

Distinct from upsell_true.py (which only ever suggests a HIGHER-priced,
meaningfully-better alternative) and complete_the_look.py (which suggests
DIFFERENT-category complementary items). This module suggests OTHER
options in the SAME category, at a roughly similar price, purely to give
the customer more choice or encourage buying more than one (e.g. the same
t-shirt style in a different color, or a comparable alternative brand).
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
                print(f"[similar_items] Tool-call JSON parse failed, retrying (attempt {attempt + 1})...")
                time.sleep(0.5)
                continue
            raise


# "Similar" price band — not premium (that's upsell_true.py's job), just
# roughly comparable so the alternative doesn't feel like a mismatched
# suggestion (e.g. a ₹300 t-shirt vs a ₹3000 "similar" one).
PRICE_BAND_MIN_MULTIPLIER = 0.5
PRICE_BAND_MAX_MULTIPLIER = 2.0

NUM_CANDIDATES_TO_SHOW = 10  # increased so there's real room to pick up to MAX_SUGGESTIONS good ones
MAX_SUGGESTIONS = 5  # cap: how many alternatives can be shown at once


def find_similar_candidates(main_product, all_products):
    """
    Filters to same-category, similarly-priced, in-stock, decently-rated
    alternatives — excluding the main product itself.
    """
    min_price = main_product["price"] * PRICE_BAND_MIN_MULTIPLIER
    max_price = main_product["price"] * PRICE_BAND_MAX_MULTIPLIER

    candidates = [
        p for p in all_products
        if p["category"] == main_product["category"]
        and p["id"] != main_product["id"]
        and p["stock"] > 0
        and p["rating"] >= 3.5
        and min_price <= p["price"] <= max_price
    ]
    # Prefer higher-rated options first among the similarly-priced pool.
    candidates.sort(key=lambda p: -p["rating"])
    return candidates[:NUM_CANDIDATES_TO_SHOW]


SIMILAR_ITEMS_TOOL = {
    "type": "function",
    "function": {
        "name": "record_similar_items_decision",
        "description": "Records which similar/alternative same-category items (if any) to show the customer.",
        "parameters": {
            "type": "object",
            "properties": {
                "suggested_product_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": f"IDs of genuinely worthwhile alternatives to show, up to {MAX_SUGGESTIONS}. Empty array if none add real variety/value."
                },
                "reasoning": {
                    "type": "string",
                    "description": "Explanation of why each was included or excluded, for the audit trail."
                }
            },
            "required": ["suggested_product_ids", "reasoning"]
        }
    }
}

SIMILAR_ITEMS_SYSTEM_PROMPT = f"""You are a shopping assistant deciding whether \
to show the customer other similar options in the SAME category as something \
they've already chosen — not an upgrade, just genuine alternatives (e.g. a \
similar t-shirt in a different color, or a comparable style from another \
brand at a similar price).

Rules you must follow:
1. Only suggest an alternative if it offers genuine variety worth showing —
   a meaningfully different color, pattern, or style. Do NOT suggest a
   near-identical duplicate of the main product (e.g. the exact same
   design in a barely-different shade).
2. Suggest at most {MAX_SUGGESTIONS} alternatives — enough to give real
   choice without overwhelming the customer.
3. If none of the candidates offer genuine variety or value, return an
   empty list. Do not suggest alternatives just to fill a quota.
4. Keep your reasoning concise but cover your decision for each candidate
   briefly — a short sentence per point, not a long paragraph.
5. Use plain ASCII punctuation only in your reasoning — regular hyphens (-)
   and straight quotes ('  "), never typographic dashes, curly/smart quotes,
   or other special Unicode punctuation. This keeps your output valid,
   parseable JSON.
6. You must call the record_similar_items_decision tool exactly once."""


def decide_similar_items(main_product, all_products):
    candidates = find_similar_candidates(main_product, all_products)

    if not candidates:
        return {
            "suggested_product_ids": [],
            "reasoning": "No same-category products found within a comparable price range and rating threshold.",
        }

    candidate_lines = "\n".join(
        f"- id: {c['id']} | {c['name']} | price: ₹{c['price']} | rating: {c['rating']}"
        for c in candidates
    )

    user_message = (
        f"Customer is looking at: {main_product['name']} "
        f"(price: ₹{main_product['price']}, rating: {main_product['rating']})\n\n"
        f"Similar-category alternatives:\n{candidate_lines}\n\n"
        f"Decide which (if any) offer genuine worthwhile variety to show. "
        f"Use plain ASCII punctuation only."
    )

    response = call_llm_with_retry(
        model=MODEL_NAME,
        messages=[
            {"role": "system", "content": SIMILAR_ITEMS_SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
        tools=[SIMILAR_ITEMS_TOOL],
        tool_choice="required",
        temperature=0.3,
        max_tokens=1200,
    )

    tool_call = response.choices[0].message.tool_calls[0]
    decision = json.loads(tool_call.function.arguments)

    # Code-level safety net: validity + hard cap enforcement.
    valid_ids = {c["id"] for c in candidates}
    filtered = [pid for pid in decision.get("suggested_product_ids", []) if pid in valid_ids]
    decision["suggested_product_ids"] = filtered[:MAX_SUGGESTIONS]

    return decision


if __name__ == "__main__":
    import random

    CATALOG_PATH = Path(__file__).parent.parent / "backend" / "data" / "catalog.json"
    with open(CATALOG_PATH, "r", encoding="utf-8") as f:
        catalog = json.load(f)
    all_products = catalog["products"]

    random.seed(4)
    in_stock = [p for p in all_products if p["stock"] > 0]
    sample = random.sample(in_stock, min(20, len(in_stock)))

    successes = 0
    total_suggested = 0
    for main in sample:
        result = decide_similar_items(main, all_products)
        n = len(result["suggested_product_ids"])
        total_suggested += n
        if n > 0:
            successes += 1
        print(f"{main['name'][:45]} (₹{main['price']}) -> {n} similar item(s): {result['suggested_product_ids']}")

    print(f"\nProducts with at least one similar-item suggestion: {successes}/{len(sample)}")
    print(f"Total similar items suggested: {total_suggested}")