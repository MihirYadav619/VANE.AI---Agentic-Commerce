"""
Phase 3 - Step 2 (revised): "Complete the Look" — multi-item complementary
suggestions with priority-ranking.

Key design decisions (from testing/debugging):
1. Supports 0 to several suggested items, one per "outfit slot"
   (topwear, bottomwear, footwear, accessory, etc.) — not a fixed count.
2. No strict "25% of main price" budget cap — real spend-bounding happens
   at the order-total / addons-budget level in policy_engine.py (Phase 4),
   not a tight per-item rule here. Only a loose 5x sanity-check blocks
   genuinely absurd mismatches.
3. ONE ITEM PER SLOT: a real outfit has one top, one pair of shoes, one
   accessory — not three competing tops. Each candidate is tagged with
   its "slot" so the LLM can enforce this rule explicitly.
4. PRIORITY-RANKED: the LLM ranks its suggestions by importance
   (priority_rank: 1 = most valuable). This lets policy_engine.py decide
   which items to keep first if the customer's stated addons-budget can't
   fit everything — instead of an arbitrary list-order.
"""

import json
import os
from pathlib import Path

from dotenv import load_dotenv

ENV_PATH = Path(__file__).parent.parent / "backend" / ".env"
load_dotenv(dotenv_path=ENV_PATH)

try:
    from mistralai.client import Mistral
except ImportError:
    from mistralai import Mistral

MODEL_NAME = "mistral-small-2603"
client = Mistral(api_key=os.environ["MISTRAL_API_KEY"])

MAX_SANITY_PRICE_MULTIPLIER = 5.0

CATEGORY_TO_SLOT = {
    "Shirts": "topwear", "Tshirts": "topwear", "Tops": "topwear", "Jackets": "topwear", "Kurtis": "topwear",
    "Jeans": "bottomwear", "Track Pants": "bottomwear", "Palazzos": "bottomwear", "Trousers": "bottomwear",
    "Lounge Pants": "bottomwear", "Leggings": "bottomwear", "Shorts": "bottomwear", "Tights": "bottomwear",
    "Jeggings": "bottomwear", "Thermal Bottoms": "bottomwear",
    "Sarees": "ethnicwear", "Kurtas": "ethnicwear", "Kurta Sets": "ethnicwear", "Sherwani": "ethnicwear",
    "Saree Blouse": "ethnicwear", "Lehenga Choli": "ethnicwear", "Ethnic Dresses": "ethnicwear",
    "Shawl": "ethnicwear", "Scarves": "ethnicwear", "Dress Material": "ethnicwear", "Clothing Set": "ethnicwear",
    "Watches": "accessory", "Wallets": "accessory", "Watch Gift Set": "accessory",
    "Earrings": "accessory", "Travel Accessory": "accessory", "Trolley Bag": "accessory",
    "Laptop Bag": "accessory",
    "Sandals": "footwear", "Boots": "footwear", "Flats": "footwear", "Sports Shoes": "footwear",
    "Dresses": "dress", "Jumpsuit": "dress", "Rompers": "dress", "Co-Ords": "dress", "Skirts": "dress",
    "Shapewear": "innerwear", "Lingerie Set": "innerwear", "Socks": "innerwear", "Briefs": "innerwear",
    "Shampoo": "personalcare", "Conditioner": "personalcare", "Lipstick": "personalcare",
    "Serum and Gel": "personalcare", "Shaving Cream and Foam": "personalcare", "Setting Spray": "personalcare",
    "Teether": "baby",
}


COMPLETE_LOOK_TOOL = {
    "type": "function",
    "function": {
        "name": "record_complete_the_look_decision",
        "description": "Records which complementary items (if any) to suggest alongside the main purchase, ranked by priority.",
        "parameters": {
            "type": "object",
            "properties": {
                "suggested_items": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "product_id": {"type": "string"},
                            "priority_rank": {
                                "type": "integer",
                                "description": "1 = most important/valuable addition to this outfit, higher numbers = less critical. Used to decide which items to keep if budget doesn't allow all of them."
                            }
                        },
                        "required": ["product_id", "priority_rank"]
                    },
                    "description": "Suggested candidates ranked by priority (1 = most important) — at most ONE per slot. Empty array if none are genuinely relevant."
                },
                "reasoning": {
                    "type": "string",
                    "description": "Clear explanation covering all candidates — why each was included/excluded and why it was ranked where it was, for the audit trail."
                }
            },
            "required": ["suggested_items", "reasoning"]
        }
    }
}

COMPLETE_LOOK_SYSTEM_PROMPT = """You are a shopping assistant deciding which \
complementary items (if any) to suggest alongside a customer's main purchase, \
to help "complete the look" (e.g. a shirt + trousers + a watch).

You will be given the main product and a list of candidate complementary \
items, each tagged with a "slot" (e.g. topwear, footwear, accessory). These \
candidates come from a category-pairing rule in the catalog — they are \
HINTS, not guaranteed good suggestions. You must judge each one yourself.

Rules you must follow:
1. Only include a candidate if it is a genuinely sensible pairing with the
   main product — items a real customer would plausibly buy together to
   complete an outfit or use case. Reject candidates that are a poor style
   match (e.g. a casual item paired with a formal one) even if the catalog
   flagged them as a category-pair.
2. NEVER suggest more than ONE candidate per "slot". A real outfit has one
   top, one pair of shoes, one accessory — not three competing tops or two
   watches. If multiple candidates fill the same slot, pick only the single
   best one for that slot and exclude the rest, even if several are
   individually reasonable.
3. You may suggest anywhere from 0 to one-per-available-slot — whatever
   forms a genuinely coherent, sensible set. Do not suggest a candidate
   just to fill a quota.
3a. When suggesting multiple items, assign each a priority_rank (1 = most
    valuable/important addition, higher = less critical). This determines
    which items get kept if the customer's budget can't fit all of them,
    so rank thoughtfully based on genuine outfit-completion value.
4. A candidate priced noticeably higher than the main item can still be a
   reasonable suggestion, as long as the combination feels like a normal
   purchase. Only reject on price grounds if the jump seems absurd.
5. Keep your reasoning concise but cover every candidate you were given.
6. You must call the record_complete_the_look_decision tool exactly once."""


def get_sane_candidates(main_product, catalog_products_by_id):
    candidate_ids = main_product.get("complementary_items", [])
    candidates = []
    for cid in candidate_ids:
        c = catalog_products_by_id.get(cid)
        if c is None:
            continue
        if c["stock"] == 0:
            continue
        if c["price"] > main_product["price"] * MAX_SANITY_PRICE_MULTIPLIER:
            continue
        candidates.append(c)
    return candidates


def decide_complete_the_look(main_product, catalog_products_by_id):
    candidates = get_sane_candidates(main_product, catalog_products_by_id)

    if not candidates:
        return {
            "suggested_product_ids": [],
            "reasoning": "No complementary candidates passed basic sanity checks (in stock, reasonable price).",
        }

    candidate_lines = "\n".join(
        f"- id: {c['id']} | {c['name']} | category: {c['category']} | "
        f"slot: {CATEGORY_TO_SLOT.get(c['category'], 'other')} | "
        f"price: ₹{c['price']} | stock: {c['stock']}"
        for c in candidates
    )

    user_message = (
        f"Main product being purchased: {main_product['name']} "
        f"(category: {main_product['category']}, price: ₹{main_product['price']})\n\n"
        f"Candidate complementary items:\n{candidate_lines}\n\n"
        f"Decide which of these (if any) to suggest as add-ons, ranked by priority. Remember: at most ONE per slot."
    )

    response = client.chat.complete(
        model=MODEL_NAME,
        messages=[
            {"role": "system", "content": COMPLETE_LOOK_SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
        tools=[COMPLETE_LOOK_TOOL],
        tool_choice="any",
        max_tokens=1000,
    )

    tool_call = response.choices[0].message.tool_calls[0]
    decision = json.loads(tool_call.function.arguments)

    # Sort by priority_rank (ascending, so rank 1 comes first) before
    # applying validity/slot-uniqueness checks.
    raw_items = decision.get("suggested_items", [])
    raw_items.sort(key=lambda x: x["priority_rank"])

    valid_ids = {c["id"] for c in candidates}
    filtered_items = [item for item in raw_items if item["product_id"] in valid_ids]

    # Code-level safety net: enforce "one per slot" in code too, in case
    # the LLM violates its own instruction. Since filtered_items is
    # already priority-sorted, keeping the first-seen per slot
    # automatically keeps the highest-priority item for that slot.
    seen_slots = set()
    final_ids = []
    for item in filtered_items:
        pid = item["product_id"]
        product = catalog_products_by_id[pid]
        slot = CATEGORY_TO_SLOT.get(product["category"], "other")
        if slot in seen_slots:
            continue
        seen_slots.add(slot)
        final_ids.append(pid)

    if len(final_ids) != len(raw_items):
        decision["reasoning"] += " (Note: some suggested ids were dropped by a code-level validity/slot-uniqueness check.)"

    # suggested_product_ids is now priority-ordered (rank 1 first) — this
    # is what policy_engine.py's budget-allocation loop consumes, so it
    # automatically respects priority without any change needed there.
    decision["suggested_product_ids"] = final_ids

    return decision


if __name__ == "__main__":
    import random

    CATALOG_PATH = Path(__file__).parent.parent / "backend" / "data" / "catalog.json"
    with open(CATALOG_PATH, "r", encoding="utf-8") as f:
        catalog = json.load(f)
    products_by_id = {p["id"]: p for p in catalog["products"]}

    random.seed(3)
    eligible = [p for p in catalog["products"] if p["stock"] > 0 and p["complementary_items"]]
    sample = random.sample(eligible, min(10, len(eligible)))

    for main in sample:
        result = decide_complete_the_look(main, products_by_id)
        print(f"\n{main['name'][:50]} (₹{main['price']}) -> {result['suggested_product_ids']}")
        print(f"  Reasoning: {result['reasoning'][:300]}")