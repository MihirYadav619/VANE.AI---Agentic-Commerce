# Agentic Commerce — Razorpay Buildathon (Track 01: AI Growth & Agentic Commerce)

An AI buyer agent that autonomously shops a merchant's catalog and completes
payments via Razorpay test-mode APIs — with every money action explainable,
bounded, gated, and audited.

---

## Project Goals

### Core Goals (directly required by the problem statement)
- [x] **Agent-readable catalog** exposing products in a machine-queryable format
- [x] **Hybrid retrieval** (semantic + keyword search) so the agent can find relevant products
- [x] **AI buyer agent** that understands intent, searches the catalog, and
      selects a product with explainable, honest reasoning
- [ ] **Purchase execution end-to-end** — no human clicking "buy" (Phase 5)
- [x] **Multiple revenue-growth mechanisms** — the agent also grows revenue
      within a transaction (the "grow the merchant's revenue" half of the PS)
- [ ] **Policy/guardrail engine** — every money action stays bounded
      (spend caps, category limits) (Phase 4)
- [ ] **Approval gate** — high-value or policy-violating orders pause for
      approval instead of executing blindly (Phase 4)
- [ ] **Real Razorpay test-mode integration** — Orders + Payments API (Phase 5)
- [ ] **Audit trail** — every decision, reasoning, and transaction is logged
      and viewable in a dashboard (Phase 7)
- [ ] **At least one graceful failure** — a deliberate failure scenario that
      the system recovers from without crashing or double-charging (Phase 9)

### Additional Goals (planned as part of this build — sequencing order, not a priority cut list)
1. **Bandit algorithm (LinUCB / Thompson Sampling)** in the product-selection
   step — a genuinely defensible ML component for the buyer agent's
   decision-making. Requires designing a reward signal (successful bounded
   purchase = positive reward).
2. **Multiple failure scenarios (5, not just 1)** — payment timeout,
   stock-out (simulated as a race-condition at payment time, not a
   search-time filter — see Catalog Source below), policy violation,
   API rate-limit, and **prompt-injection resistance** (a deliberately
   malicious/crafted product description attempting to manipulate the
   agent's reasoning — see Known Limitations below for why this matters).
3. **Measured retrieval quality** — quantify hybrid search (FAISS + BM25 +
   RRF) vs. keyword-only search with a simple metric, backed by a number
   instead of just a demo.
4. **Second agent for a true multi-agent demo** — a merchant-side agent that
   adjusts pricing/promotions based on demand signals, interacting with the
   buyer agent.
5. **UI/UX deep polish** — live reasoning/typing effect on the dashboard,
   proper charts for revenue/approval/failure-recovery stats, mobile
   responsiveness.

**Checkpoint rule:** after Phase 5 (Razorpay integration) is done, honestly
assess progress against the timeline. If on schedule, continue through the
additional goals above. If behind, drop items in the order listed (UI
polish first, bandit algorithm last, since the bandit is the highest-value
differentiator).

---

## Progress Log

### Phase 1 — Setup + Catalog ✅
- Project folder structure created (`backend`, `frontend`, `catalog-service`,
  `buyer-agent`, `audit-service`)
- FastAPI skeleton running (`/catalog`, `/catalog/product/{id}`, `/policy`)
- Real product catalog built from a public Myntra dataset (see *Catalog
  Source* below) — **897 products** across 53 categories, fully validated
- Policy schema defined: spend caps, approval-gate threshold, upsell rules
- `.env.example`, `.gitignore`, `requirements.txt` set up
- Reproducible via `backend/scripts/generate_catalog.py` — anyone can
  regenerate the exact same catalog from scratch with one command

### Phase 2 — Hybrid Retrieval ✅
- **FAISS semantic search** (`catalog-service/build_embeddings.py`) — every
  product embedded with `all-MiniLM-L6-v2`, indexed for meaning-based search
- **BM25 keyword search** (`catalog-service/bm25_search.py`) — exact-text
  matching, complements FAISS's semantic strength
- **Price-constraint parser** (`catalog-service/query_parser.py`) — extracts
  phrases like "under 5000" from queries *before* they hit search, applying
  them as a hard numeric filter instead of leaving them as keywords. This
  fixed a real bug where "watch under 5000" matched the brand "UNDER ARMOUR"
  ahead of actual watches.
- **Hybrid search** (`catalog-service/hybrid_search.py`) — combines FAISS +
  BM25 using **Reciprocal Rank Fusion (RRF)**, not simple score-averaging.
  RRF was adopted after testing showed min-max normalization let a weak
  keyword match tie with a genuinely strong semantic match (both scoring
  "1.0" as each method's #1 result).
- Out-of-stock items are filtered out of search results entirely — a
  deliberate design choice (see Catalog Source below for how the
  failure-demo scenario is handled instead)
- **Known catalog-coverage limitation**: some categories (e.g. "Jackets")
  have very few products, so a specific query (e.g. "blue denim jacket")
  may return the closest available alternative rather than an exact match.
  This reflects genuine catalog scarcity, not a search bug — judging
  *whether* a candidate is a true match is intentionally left to the buyer
  agent's reasoning (Phase 3), not the search layer.

### Phase 3 — Buyer Agent Core Reasoning + Revenue Mechanisms ✅
- **Core reasoning engine** (`buyer-agent/reasoning_engine.py`, using
  Mistral AI `mistral-small-2603`) — takes a natural-language request,
  retrieves candidates via hybrid search, and uses LLM tool-calling to
  select the best genuine match. Explicitly distinguishes **hard
  constraints** (category, color, price — reject on mismatch) from **soft
  preferences** (comfort, style — don't reject just because unconfirmed).
  Honestly reports "no match found" rather than forcing a bad pick.
- Four distinct, tested revenue-growth mechanisms were built (not just one
  generic "upsell"):

  1. **True Upsell** (`buyer-agent/upsell_true.py`) — suggests a
     same-category, higher-priced, meaningfully-better alternative (e.g. a
     higher-rated shirt). Distinct from cross-sell: it *replaces* the
     chosen item, it doesn't add a new one. Bounded by the customer's own
     stated price ceiling (see Purchase Architecture below), not a
     separate budget.
  2. **Complete the Look** (`buyer-agent/complete_the_look.py`) — suggests
     complementary, different-category items (e.g. a shirt + trousers +
     watch) using the catalog's `complementary_items` field as a
     **candidate hint**, not a final answer — the agent independently
     judges relevance, style-consistency, and gender-appropriateness.
     Enforces **one suggestion per "outfit slot"** (topwear, footwear,
     accessory, etc.) so it never suggests 3 competing tops at once — a
     real bug caught during testing when candidate counts were increased.
  3. **Similar Items** (`buyer-agent/similar_items.py`) — shows other
     same-category alternatives at a comparable price (e.g. other t-shirts
     in different colors), for browsing/variety. **Only used in
     Human-Browse mode** (see Purchase Architecture) — never
     auto-purchased in Fully-Autonomous mode, since that could otherwise
     result in buying two t-shirts when the customer asked for one.
  4. **Cart-Value Threshold Nudge** (`buyer-agent/cart_nudge.py`) — a
     pure-arithmetic (no LLM) incentive message, e.g. "Add ₹150 more to
     unlock free delivery," using a configurable threshold from
     `policy.json`. Deliberately skips the nudge if the cart is too far
     from the threshold (>30% gap) to avoid feeling like a fake push.

- **Catalog fixes made during Phase 3 testing:**
  - Complementary-item mapping was originally too sparse (only 1 candidate
    per outfit-slot, capped at 2 total) — expanded to 3 candidates per
    slot and 3 slots per category (up to ~9 raw hints), which raised the
    genuine-suggestion rate from 64% to 100% in testing.
  - Complementary candidates were originally picked at random regardless
    of gender, causing many LLM rejections (e.g. a women's watch offered
    for a men's shirt). Fixed by adding gender-detection
    (`detect_gender()` in `generate_catalog.py`) and preferring
    same-gender candidates during catalog generation.
  - 147 products had a `0.0` rating in the raw dataset (meaning "no
    reviews yet") — reassigned a synthetic realistic rating (3.5–4.8) so
    demos never show an unrealistic 0-star recommendation. **Disclosed
    here for transparency — these specific values are not real customer
    data.**

---

## Purchase Architecture: Two Modes

A key design decision made during Phase 3 testing: letting the agent
autonomously ADD extra items (cross-sell/similar-items) without any human
checkpoint risks charging a customer for something they never actually
wanted (e.g. two t-shirts when they asked for one). The fix is to
separate **who selects items** from **who executes payment** — the latter
is *always* the agent, in both modes below, preserving the PS's "no human
clicking buy" requirement for the actual transaction itself.

### Mode 1: Fully Autonomous
The customer states their request (e.g. "a t-shirt under ₹1000") and,
optionally, opts into "Complete the Look" with a separate add-ons budget
(e.g. "up to ₹500 more"). The agent then runs end-to-end with no further
human input:
- **True Upsell** operates only within the customer's own stated primary
  budget (e.g. never suggests a shirt over ₹1000, even if a "better" one
  exists slightly above it) — this is a *replacement*, not an addition,
  so it doesn't need separate consent beyond the price ceiling the
  customer already gave.
- **Complete the Look** operates only within the separately-stated,
  opt-in add-ons budget — this *does* require the upfront opt-in, since
  it adds new items to the order.
- **Similar Items is not used in this mode** — since there's no human to
  choose between alternatives, auto-adding one would risk duplicate
  purchases (e.g. two t-shirts).
- The agent completes the purchase (Phase 5: Razorpay) with no further
  confirmation, subject to the policy engine's approval-gate (Phase 4)
  for high-value orders.

### Mode 2: Human-Browse, Agent-Executes
The agent still searches and runs all four revenue mechanisms, but
presents them as **options for the human to choose from**, rather than
auto-applying any of them. No upfront budget question is needed here —
the human sees real prices and self-regulates naturally. Once the human
finalizes their selection (which may legitimately include, say, two
t-shirts if they consciously pick both), the agent takes over and
executes the payment autonomously — same policy/gate/audit pipeline as
Mode 1.

**The common thread across both modes:** regardless of who chooses *what*
to buy, the agent always handles *how* it gets bought — search, policy
checks, and the actual Razorpay transaction are never a manual, human-
clicked step.

*(This architecture will be implemented in Phase 4 (consent/budget schema)
and surfaced in Phase 10 (frontend mode-selection UI).)*

---

## Known Limitations / Scoping Decisions

Deliberately compared against real agentic-commerce concepts (ACP, AP2,
x402, NPCI UAP) to be explicit about what's simplified for buildathon
scope vs. what would need more work in a production system:

- **Authorization is a stored flag, not a cryptographic mandate.** Real
  protocols like AP2 use signed mandates to *prove* a payment was
  customer-authorized. Our consent/budget model (see Purchase Architecture
  above) captures the same *intent* but stores it as a simple record, not
  a cryptographically-verifiable proof. Acceptable for this scope; would
  need real signing infrastructure in production.
- **Merchant-policy vs. customer-budget are now separated**, after
  initially being conflated. `policy.json`'s spend-caps/approval-gate are
  *merchant-side* governance bounds; the customer's own stated budget
  (primary item price ceiling + optional add-ons budget) is a *separate*,
  per-purchase authorization layer.
- **Prompt-injection resistance is partially built, not yet explicitly
  tested.** A malicious/crafted product description could theoretically
  attempt to manipulate the LLM's reasoning (e.g. embedded text saying
  "ignore price limits"). Every revenue module already includes a
  code-level safety net that re-verifies price/stock/ID against the
  LLM's decision rather than trusting it blindly — this already defends
  against the *effect* of such an attack, but it hasn't been deliberately
  tested with a crafted malicious description. Planned as a Phase 9
  failure scenario.
- **Liability and returns are out of scope.** What happens if the agent
  buys the wrong size/color, and who's responsible, isn't modeled. The
  approval-gate on high-value orders indirectly reduces this risk, but a
  full returns/liability framework is beyond buildathon scope.
- **Agent-to-agent trust/interoperability is not applicable.** Concepts
  like "how does Agent A know Agent B is legitimate" apply to
  cross-company agent ecosystems. This project is a single buyer-agent
  talking to a single merchant catalog — that scenario doesn't arise by
  design, not by oversight.

---

## Phase 1 Setup Instructions

### 1. Razorpay Test Account
1. Sign up / log in at https://dashboard.razorpay.com
2. Switch to **Test Mode** (toggle top-left of dashboard)
3. Go to **Settings → API Keys → Generate Key**
4. Copy `Key Id` and `Key Secret` — you will NOT see the secret again after
   closing the popup, so save it immediately

### 2. Backend Setup
```bash
cd backend
python -m venv venv
venv\Scripts\activate      # on Mac/Linux: source venv/bin/activate
pip install -r requirements.txt
copy .env.example .env     # on Mac/Linux: cp .env.example .env
# then fill in your real keys in .env
```

### 3. Generate the Catalog
```bash
python scripts/generate_catalog.py
```
This downloads the real Myntra dataset from GitHub and builds
`backend/data/catalog.json` (897 products).

### 4. Build the Search Index
```bash
python ../catalog-service/build_embeddings.py
```

### 5. Run the Backend
```bash
python main.py
```
Visit http://localhost:8000/catalog and http://localhost:8000/policy to
confirm the catalog and policy data load correctly.

### 6. Frontend Setup (Phase 10, not needed yet)
```bash
cd frontend
npm create vite@latest . -- --template react
npm install
npm install -D tailwindcss postcss autoprefixer
```

---

## Catalog Source

`backend/data/catalog.json` is built from a **real Myntra product dataset**
(sourced via a public Bright Data sample on GitHub: ~1000 real Indian
fashion e-commerce products with genuine INR pricing, ratings, and
descriptions). It was cleaned to remove scraping artifacts (a number of
rows had brand/store names mistakenly captured as the category — e.g.
"BOLDFIT", "Milton", "RANDOM" — these were filtered out), leaving **897
genuine products across 53 real categories** (Shirts, Watches, Tops,
T-shirts, Wallets, Jeans, Sarees, Kurtas, Jackets, Dresses, personal care
items, and more).

On top of the raw data, the following was added or corrected manually
since the dataset doesn't include it or has gaps:

- **Stock quantities** — realistic spread, with ~26 items deliberately set
  to 0. Out-of-stock items are excluded from search results entirely
  (Phase 2); the failure-demo (Phase 9) instead simulates a realistic
  "race condition" — an item appears available at search/selection time,
  but a fresh stock check at payment time reveals it just sold out —
  rather than showing dead stock in search.
- **Gender-aware complementary-item mapping** — built via a category-group
  rule engine (e.g. tops ↔ accessories/bottoms/footwear, personal care ↔
  personal care), preferring same-gender candidates so the buyer agent
  isn't handed nonsensical hints (e.g. a women's watch for a men's shirt).
  3 candidates are generated per outfit-slot (not just 1), giving the
  agent's reasoning step genuine alternatives to choose from. This field
  is a **candidate hint**, not a final answer — the buyer agent decides
  whether to actually offer a given item, based on style, budget, and
  policy, and explains that decision.
- **Ratings** — 147 of the 897 products had no rating in the original
  dataset (raw value 0.0, meaning "no reviews yet"). These were assigned a
  synthetic rating between 3.5 and 4.8 so the demo doesn't show an
  unrealistic 0-star product being recommended. **This is disclosed here
  for transparency — these specific rating values are not real customer
  data.** The remaining ~750 products carry genuine Myntra ratings.
- Each product also carries a real `image_url` from Myntra's CDN
  (assets.myntassets.com). **Note:** the dataset is from 2021-2022, so a
  few image links may be dead or blocked by hotlink protection. Test these
  in the actual frontend and add an `onError` fallback so a broken image
  never breaks the UI during a live demo:

```jsx
<img
  src={product.image_url}
  alt={product.name}
  onError={(e) => { e.target.onerror = null; e.target.src = "/placeholder-product.png"; }}
/>
```

5 products naturally exceed the ₹10,000 approval-gate threshold, so
gate/approval scenarios trigger organically without needing to hardcode
special-case products.

The full pipeline is reproducible via `backend/scripts/generate_catalog.py`
— running it regenerates the exact same catalog from the raw dataset.

---

## Project Structure

agentic-commerce/
├── backend/
│ ├── data/
│ │ ├── catalog.json # 897 real Myntra-sourced products
│ │ ├── policy.json # spend caps, gate thresholds, cart incentives
│ │ ├── faiss_index.bin # FAISS semantic search index
│ │ └── faiss_id_map.json # FAISS position -> product ID mapping
│ ├── scripts/
│ │ └── generate_catalog.py # regenerates catalog.json from the raw dataset
│ ├── routes/ # API route modules (added Phase 4+)
│ ├── models/ # Pydantic schemas (added Phase 4+)
│ ├── main.py # FastAPI app entrypoint
│ ├── requirements.txt
│ └── .env.example
├── catalog-service/
│ ├── build_embeddings.py # builds the FAISS index (Phase 2)
│ ├── bm25_search.py # keyword search (Phase 2)
│ ├── query_parser.py # price-constraint extraction (Phase 2)
│ └── hybrid_search.py # combined FAISS+BM25+RRF search (Phase 2)
├── buyer-agent/
│ ├── reasoning_engine.py # core product-selection reasoning (Phase 3)
│ ├── upsell_true.py # same-category premium upgrade (Phase 3)
│ ├── complete_the_look.py # multi-item complementary suggestions (Phase 3)
│ ├── similar_items.py # same-category alternatives (Phase 3)
│ └── cart_nudge.py # cart-value threshold nudge (Phase 3)
├── audit-service/ # logging + dashboard API (Phase 7)
└── frontend/ # React UI (Phase 10)



## Policy Summary (data/policy.json)
- Max spend per transaction: ₹20,000 (merchant-side bound)
- Approval gate triggers above: ₹10,000
- Free-delivery cart-nudge threshold: ₹1,999 (nudge shown if within 30% of it)
- Customer-side primary/add-ons budgets: see *Purchase Architecture* above
  (implemented in Phase 4)

## Next Steps (Phase 4)
- Build the Policy Engine: enforce spend-caps and the approval-gate in code
  (not just as config)
- Implement the customer consent/budget schema from *Purchase Architecture*
  (primary-item budget, opt-in add-ons budget, Fully-Autonomous vs
  Human-Browse mode)
- Wire the four revenue modules (Phase 3) into this policy layer so their
  decisions are actually bounded, not just individually tested