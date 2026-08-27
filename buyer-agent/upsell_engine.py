"""
Phase 3 - Step 2: Upsell/cross-sell reasoning.

Takes the buyer agent's already-selected product and decides whether to
suggest a complementary item — using the catalog's `complementary_items`
field as a CANDIDATE HINT only, not a final answer. The agent must reason
about whether the suggestion is genuinely relevant and fits within budget/
policy, and explain that reasoning (this will feed the audit trail later).
"""

import json
import os
from pathlib import Path

from dotenv import load_dotenv

ENV_PATH = Path(__file__).parent.parent / "backend" / ".env"
load_dotenv(dotenv_path=ENV_PATH)

from mistralai.client import Mistral


MODEL_NAME = "mistral-small-2603"
client = Mistral(api_key=os.environ["MISTRAL_API_KEY"])

# Policy constants (Phase 4 will move these into the full policy engine —
# for now, hardcoding just enough to make upsell reasoning meaningful).
MAX_UPSELL_PERCENTAGE_OF_ORDER = 0.25  # upsell item can't exceed 25% of main item's price


UPSELL_TOOL = {
    "type": "function",
    "function": {
        "name": "record_upsell_decision",
        "description": "Records whether to suggest a complementary/upsell item alongside the main purchase.",
        "parameters": {
            "type": "object",
            "properties": {
                "should_suggest": {
                    "type": "boolean",
                    "description": "True if a genuinely relevant, budget-appropriate upsell exists among the candidates."
                },
                "suggested_product_id": {
                    "type": ["string", "null"],
                    "description": "The id of the upsell candidate to suggest, or null if should_suggest is false."
                },
                "reasoning": {
                    "type": "string",
                    "description": "Clear explanation of why this upsell was suggested (or why none was), for the audit trail."
                }
            },
            "required": ["should_suggest", "suggested_product_id", "reasoning"]
        }
    }
}

UPSELL_SYSTEM_PROMPT = """You are a shopping assistant deciding whether to \
suggest ONE complementary add-on item alongside a customer's main purchase.

You will be given:
- The main product the customer is buying
- A list of "candidate" complementary items (these are catalog HINTS from a
  category-pairing rule — they are NOT guaranteed to be good suggestions,
  you must judge that yourself)
- The maximum allowed price for the upsell item (a hard budget constraint)

Rules you must follow:
1. Only suggest a candidate if it is genuinely a sensible pairing with the
   main product (e.g. a watch or wallet alongside a shirt makes sense; two
   unrelated items do not, even if the catalog listed them as a candidate).
2. NEVER suggest an item priced above the given maximum — this is a hard
   budget rule, not a preference.
3. If no candidate is both relevant AND within budget, set should_suggest
   to false. Do not force a suggestion just because candidates exist.
4. Keep your reasoning concise (1-2 sentences).
5. You must call the record_upsell_decision tool exactly once."""


def decide_upsell(main_product, catalog_products_by_id):
    """
    main_product: the full product dict that was already selected as the
                  main purchase (from reasoning_engine.py's decide())
    catalog_products_by_id: dict of {product_id: product_dict} for the
                  whole catalog, so we can look up complementary_items
    """
    candidate_ids = main_product.get("complementary_items", [])
    candidates = [catalog_products_by_id[cid] for cid in candidate_ids if cid in catalog_products_by_id]

    if not candidates:
        return {
            "should_suggest": False,
            "suggested_product_id": None,
            "reasoning": "No complementary candidates exist for this product in the catalog.",
        }

    max_upsell_price = round(main_product["price"] * MAX_UPSELL_PERCENTAGE_OF_ORDER)

    candidate_lines = "\n".join(
        f"- id: {c['id']} | {c['name']} | category: {c['category']} | price: ₹{c['price']} | stock: {c['stock']}"
        for c in candidates
    )

    user_message = (
        f"Main product being purchased: {main_product['name']} "
        f"(category: {main_product['category']}, price: ₹{main_product['price']})\n\n"
        f"Candidate complementary items:\n{candidate_lines}\n\n"
        f"Maximum allowed price for the upsell item: ₹{max_upsell_price}\n\n"
        f"Decide whether to suggest one of these as an add-on."
    )

    response = client.chat.complete(
        model=MODEL_NAME,
        messages=[
            {"role": "system", "content": UPSELL_SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
        tools=[UPSELL_TOOL],
        tool_choice="any",
    )

    tool_call = response.choices[0].message.tool_calls[0]
    decision = json.loads(tool_call.function.arguments)

    # Safety net: even though the prompt tells the LLM the budget rule, we
    # don't fully trust LLM arithmetic (we saw it make a price mistake in
    # Phase 3 - Step 1 testing). So we double check in code before
    # returning should_suggest=True.
    if decision["should_suggest"]:
        suggested = next((c for c in candidates if c["id"] == decision["suggested_product_id"]), None)
        if suggested is None or suggested["price"] > max_upsell_price or suggested["stock"] == 0:
            decision["should_suggest"] = False
            decision["suggested_product_id"] = None
            decision["reasoning"] += " (Overridden by code-level safety check: candidate failed budget or stock validation.)"

    return decision


if __name__ == "__main__":
    # Quick manual test using a couple of catalog products directly,
    # without needing the full reasoning_engine pipeline.
    CATALOG_PATH = Path(__file__).parent.parent / "backend" / "data" / "catalog.json"
    with open(CATALOG_PATH, "r", encoding="utf-8") as f:
        catalog = json.load(f)
    products_by_id = {p["id"]: p for p in catalog["products"]}

    test_product_ids = ["M0244", "M0401", "M0485"]  # a shirt, a watch, a kurta from earlier tests

    for pid in test_product_ids:
        main = products_by_id[pid]
        print(f"\n{'='*60}\nMain product: {main['name']} (₹{main['price']})")
        result = decide_upsell(main, products_by_id)
        print(json.dumps(result, indent=2))