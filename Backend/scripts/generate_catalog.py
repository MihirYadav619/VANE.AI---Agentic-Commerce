"""
One-time setup script: downloads the real Myntra product dataset from
GitHub, cleans it, and generates backend/data/catalog.json.

Run this once from the backend/ directory:
    python scripts/generate_catalog.py

Requires: pandas (pip install pandas)
"""

import json
import re
import random
import urllib.request
from pathlib import Path

import pandas as pd

random.seed(42)

RAW_DATA_URL = "https://raw.githubusercontent.com/luminati-io/myntra-dataset-sample/main/Myntra%20products%20.csv"
SCRIPT_DIR = Path(__file__).parent
RAW_CSV_PATH = SCRIPT_DIR / "myntra_raw.csv"
OUTPUT_PATH = SCRIPT_DIR.parent / "data" / "catalog.json"


def download_dataset():
    if RAW_CSV_PATH.exists():
        print(f"Raw dataset already downloaded at {RAW_CSV_PATH}")
        return
    print("Downloading Myntra dataset from GitHub...")
    urllib.request.urlretrieve(RAW_DATA_URL, RAW_CSV_PATH)
    print("Download complete.")


def get_category(breadcrumb_str):
    try:
        crumbs = json.loads(breadcrumb_str)
        names = [c["name"] for c in crumbs]
        return names[2] if len(names) > 2 else (names[-1] if names else "Unknown")
    except Exception:
        return "Unknown"


def clean_price(p):
    try:
        return round(float(str(p).replace('"', "").replace("₹", "").replace(",", "").strip()))
    except Exception:
        return None


def clean_text(s, maxlen=200):
    if pd.isna(s):
        return ""
    s = str(s).strip()
    s = re.sub(r"\s+", " ", s)
    return s[:maxlen]


def first_image(images_str):
    try:
        imgs = json.loads(images_str)
        if imgs:
            return imgs[0].replace("http://", "https://")
    except Exception:
        pass
    return None


def detect_gender(product_name):
    """
    Extracts an implied gender tag from a product name, so complementary-
    item selection can avoid pairing e.g. a women's watch with a men's
    shirt. Such mismatches get correctly rejected by the LLM downstream,
    but that wastes a candidate slot that could have gone to a genuinely
    usable, same-gender pairing instead.
    """
    name_lower = product_name.lower()
    if re.search(r"\bmen\b", name_lower) and "women" not in name_lower:
        return "men"
    if "women" in name_lower:
        return "women"
    if re.search(r"\bboys?\b", name_lower):
        return "boys"
    if re.search(r"\bgirls?\b", name_lower):
        return "girls"
    return "unisex"

def get_gender_from_breadcrumb(breadcrumb_str):
    """
    More reliable than parsing the product NAME — Myntra's breadcrumb
    hierarchy consistently states gender near the top (e.g. "Men >
    Clothing > Topwear"), whereas titles often omit it entirely when
    implied by category (e.g. "Styli Pink Mandarin Collar Lace Insert
    Top" never says "Women", causing name-based detection to default it
    to "unisex" and incorrectly let it pass a gender-mismatch filter).
    """
    try:
        crumbs = json.loads(breadcrumb_str)
        names = [c["name"].lower() for c in crumbs]
        joined = " ".join(names[:2])
        if "women" in joined:
            return "women"
        if "men" in joined:
            return "men"
        if "boys" in joined:
            return "boys"
        if "girls" in joined:
            return "girls"
    except Exception:
        pass
    return None
# Brand/store names that got mistakenly captured as "category" during
# scraping (breadcrumb depth was inconsistent for these rows) — not real
# product categories, so they're excluded.
JUNK_CATEGORIES = {
    "Trunk", "Milton", "RANDOM", "Creeva", "eCraftIndia", "BOLDFIT",
    "MR. COPPER KING", "Art Street", "DULI", "HOOM", "ROMEE",
    "SEJ by Nisha Gupta", "Saral Home", "JASMEY HOMES", "AEROHAVEN",
    "Devansh", "The Art House", "999Store", "AAKRITI ART CREATIONS",
    "GOODHOMES", "ellementry", "nestroots", "KLOTTHE", "Alina decor",
    "Indigifts", "Homesake", "BLANC9", "Lock & Lock", "Treo", "Disney",
    "ExclusiveLane", "Unknown",
}

# Broad category groups used to build sensible complementary-item pairs.
CATEGORY_GROUP = {
    "Shirts": "top", "Tshirts": "top", "Tops": "top", "Jackets": "top", "Kurtis": "top",
    "Jeans": "bottom", "Track Pants": "bottom", "Palazzos": "bottom", "Trousers": "bottom",
    "Lounge Pants": "bottom", "Leggings": "bottom", "Shorts": "bottom", "Tights": "bottom",
    "Jeggings": "bottom", "Thermal Bottoms": "bottom",
    "Sarees": "ethnic", "Kurtas": "ethnic", "Kurta Sets": "ethnic", "Sherwani": "ethnic",
    "Saree Blouse": "ethnic", "Lehenga Choli": "ethnic", "Ethnic Dresses": "ethnic",
    "Shawl": "ethnic", "Scarves": "ethnic", "Dress Material": "ethnic", "Clothing Set": "ethnic",
    "Watches": "accessory", "Wallets": "accessory", "Watch Gift Set": "accessory",
    "Earrings": "accessory", "Travel Accessory": "accessory", "Trolley Bag": "accessory",
    "Laptop Bag": "accessory",
    "Sandals": "footwear", "Boots": "footwear", "Flats": "footwear", "Sports Shoes": "footwear",
    "Dresses": "dress", "Jumpsuit": "dress", "Rompers": "dress", "Co-Ords": "dress", "Skirts": "dress",
    "Shapewear": "innerwear", "Lingerie Set": "innerwear", "Socks": "innerwear", "Briefs": "innerwear",
    "Shampoo": "personalcare", "Conditioner": "personalcare", "Lipstick": "personalcare",
    "Serum and Gel": "personalcare", "Shaving Cream and Foam": "personalcare",
    "Setting Spray": "personalcare",
    "Teether": "baby",
}

# Which groups can complement which other groups. Expanded so a full
# "head-to-toe" outfit (top + bottom + footwear + accessory) is possible
# for garment categories, and so accessories/footwear can also suggest a
# complete outfit around themselves — consistent 3-group mapping wherever
# it makes sense. "dress" is an intentional exception: a dress is already
# a complete top+bottom garment, so pairing it with another top/bottom
# doesn't make sense — it only gets accessory + footwear.
COMPLEMENT_GROUP_RULES = {
    "top": ["bottom", "footwear", "accessory"],
    "bottom": ["top", "footwear", "accessory"],
    "ethnic": ["bottom", "accessory", "footwear"],
    "accessory": ["top", "bottom", "footwear"],
    "footwear": ["top", "bottom", "accessory"],
    "dress": ["accessory", "footwear"],  # intentional 2-group exception, see comment above
    "innerwear": ["top"],
    "personalcare": ["personalcare"],
    "baby": [],
    "misc": [],
}

STOCK_POOL = [45, 30, 60, 22, 15, 80, 38, 50, 12, 27, 90, 33, 65, 18, 55]
OUT_OF_STOCK_FRACTION = 0.03  # ~3% of products deliberately out of stock


def build_catalog():
    df = pd.read_csv(RAW_CSV_PATH)
    df["sub_category"] = df["breadcrumbs"].apply(get_category)
    df["price_clean"] = df["final_price"].apply(clean_price)

    df = df[~df["sub_category"].isin(JUNK_CATEGORIES)].copy()
    df = df.dropna(subset=["price_clean"])
    df = df.drop_duplicates(subset=["title", "product_description"])
    df = df.reset_index(drop=True)

    print(f"Clean rows after filtering junk categories & duplicates: {len(df)}")

    products = []
    for i, row in df.iterrows():
        pid = f"M{i + 1:04d}"
        name = clean_text(f"{row['title']} {row['product_description']}", 80)
        raw_rating = float(row["rating"]) if pd.notna(row["rating"]) else 0.0
        products.append({
            "id": pid,
            "name": name,
            "category": row["sub_category"],
            "price": int(row["price_clean"]),
            "rating": raw_rating,
            "description": clean_text(row["product_description"], 200),
            "image_url": first_image(row["images"]),
            "_group": CATEGORY_GROUP.get(row["sub_category"], "misc"),
            "gender": get_gender_from_breadcrumb(row["breadcrumbs"]) or detect_gender(name),
        })

    # Fix zero/missing ratings -> assign a realistic value instead of 0.0,
    # since a "0.0 rating" product being recommended live looks broken even
    # though the underlying data is just "no reviews yet".
    for p in products:
        if p["rating"] == 0.0:
            p["rating"] = round(random.uniform(3.5, 4.8), 1)

    # Assign stock quantities, with a small deliberate fraction at 0
    # (used for the graceful-failure demo scenario).
    for p in products:
        p["stock"] = random.choice(STOCK_POOL)

    n_out_of_stock = max(5, int(len(products) * OUT_OF_STOCK_FRACTION))
    out_indices = random.sample(range(len(products)), n_out_of_stock)
    for idx in out_indices:
        products[idx]["stock"] = 0

        # Build complementary-item mapping via category groups, preferring
    # candidates that share the main product's gender (or are unisex) so
    # the buyer agent isn't handed nonsensical gender-mismatched hints.
    #
    # We pick up to CANDIDATES_PER_GROUP items from EACH complement-group
    # (not just 1) so the buyer agent's reasoning step has real
    # alternatives to choose from within each outfit "slot" — e.g. if one
    # randomly-picked footwear candidate happens to be a style mismatch,
    # there are 2 more footwear options to consider instead of none.
    CANDIDATES_PER_GROUP = 3

    products_by_id = {p["id"]: p for p in products}
    by_group = {}
    for p in products:
        by_group.setdefault(p["_group"], []).append(p["id"])

    for p in products:
        comp_groups = COMPLEMENT_GROUP_RULES.get(p["_group"], [])
        comp_ids = []
        for cg in comp_groups:
            pool = [pid for pid in by_group.get(cg, []) if pid != p["id"]]
            if not pool:
                continue

            if p["gender"] == "unisex":
                chosen_pool = pool
            else:
                same_gender_pool = [
                    pid for pid in pool
                    if products_by_id[pid]["gender"] in (p["gender"], "unisex")
                ]
                chosen_pool = same_gender_pool if same_gender_pool else pool

            # Pick up to CANDIDATES_PER_GROUP unique candidates from this group.
            n_pick = min(CANDIDATES_PER_GROUP, len(chosen_pool))
            comp_ids.extend(random.sample(chosen_pool, n_pick))

        p["complementary_items"] = comp_ids

    # Clean up temporary fields ONLY after every product has finished
    # computing its complementary_items — deleting them earlier (inside
    # the loop above) breaks later iterations that still need to look up
    # an EARLIER product's _gender/_group as a candidate.
    for p in products:
        del p["_group"]

    return products

def validate(products):
    all_ids = {p["id"] for p in products}
    broken = [
        (p["id"], cid) for p in products
        for cid in p["complementary_items"] if cid not in all_ids
    ]
    high_value = sum(1 for p in products if p["price"] > 10000)
    out_of_stock = sum(1 for p in products if p["stock"] == 0)
    missing_images = sum(1 for p in products if not p.get("image_url"))
    no_complements = sum(1 for p in products if not p["complementary_items"])
    zero_ratings = sum(1 for p in products if p["rating"] == 0.0)

    print(f"\nTotal products: {len(products)}")
    print(f"Categories: {len(set(p['category'] for p in products))}")
    print(f"Broken complementary refs: {len(broken)}")
    print(f"Products with NO complementary item: {no_complements}")
    print(f"Zero-rating products remaining: {zero_ratings}")
    print(f"Out of stock: {out_of_stock}")
    print(f"High value (>10000): {high_value}")
    print(f"Missing images: {missing_images}")


def main():
    download_dataset()
    products = build_catalog()
    validate(products)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump({"products": products}, f, indent=2, ensure_ascii=False)

    print(f"\ncatalog.json written to: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()