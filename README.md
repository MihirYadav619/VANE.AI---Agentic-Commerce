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
- [x] **Purchase execution end-to-end** — no human clicking "buy" for the
      actual transaction (Razorpay Orders API integrated; payment collection
      goes through Razorpay Checkout, verified server-side)
- [x] **Multiple revenue-growth mechanisms** — the agent also grows revenue
      within a transaction (the "grow the merchant's revenue" half of the PS)
- [x] **Policy/guardrail engine** — every money action stays bounded
      (customer-stated budgets, merchant-side spend caps)
- [x] **Approval gate** — high-value or policy-violating orders pause for
      approval instead of executing blindly
- [x] **Real Razorpay test-mode integration** — Orders API + Checkout +
      signature verification, fully tested end-to-end
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
   search-time filter), policy violation, API rate-limit, and
   **prompt-injection resistance** (a deliberately malicious/crafted product
   description attempting to manipulate the agent's reasoning).
3. **Measured retrieval quality** — quantify hybrid search (FAISS + BM25 +
   RRF) vs. keyword-only search with a simple metric, backed by a number
   instead of just a demo.
4. **Second agent for a true multi-agent demo** — a merchant-side agent that
   adjusts pricing/promotions based on demand signals, interacting with the
   buyer agent.
5. **UI/UX deep polish** — live reasoning/typing effect on the dashboard,
   proper charts for revenue/approval/failure-recovery stats, mobile
   responsiveness.

**Checkpoint (completed after Phase 5):** Progress assessed as comfortably
on-time. Proceeding with the full additional-goals list above as originally
planned, in the order listed.

---

## Progress Log

### Phase 1 — Setup + Catalog ✅
- Project folder structure created (`backend`, `frontend`, `catalog-service`,
  `buyer-agent`, `audit-service`)
- FastAPI skeleton running (`/catalog`, `/catalog/product/{id}`, `/policy`)
- Real product catalog built from a public Myntra dataset (see *Catalog
  Source* below) — **897 products** across 53 categories, fully validated
- Policy schema defined: spend caps, approval-gate threshold, upsell rules
- Reproducible via `backend/scripts/generate_catalog.py`

### Phase 2 — Hybrid Retrieval ✅
- **FAISS semantic search**, **BM25 keyword search**, and a **price-constraint
  parser** (fixed a real bug where "watch under 5000" matched the brand
  "UNDER ARMOUR" ahead of actual watches)
- **Hybrid search** combines FAISS + BM25 using **Reciprocal Rank Fusion
  (RRF)**, adopted after testing showed min-max normalization let a weak
  keyword match tie with a genuinely strong semantic match
- Out-of-stock items are filtered out of search entirely — the failure-demo
  (Phase 9) instead simulates a realistic race-condition at payment time
- **Known catalog-coverage limitation**: some categories have very few
  products, so specific queries may return the closest available
  alternative — judging *whether* a candidate is a true match is
  intentionally left to the buyer agent's reasoning, not the search layer

### Phase 3 — Buyer Agent Core Reasoning + Revenue Mechanisms ✅
- **Core reasoning engine** (`buyer-agent/reasoning_engine.py`, Mistral AI
  `mistral-small-2603`) — retrieves candidates via hybrid search, uses LLM
  tool-calling to select the best genuine match. Distinguishes **hard
  constraints** (reject on mismatch) from **soft preferences** (don't reject
  just because unconfirmed). Honestly reports "no match found" rather than
  forcing a bad pick.
- Four distinct, tested revenue-growth mechanisms:
  1. **True Upsell** (`upsell_true.py`) — same-category, higher-priced,
     meaningfully-better alternative. *Replaces* the chosen item rather
     than adding a new one.
  2. **Complete the Look** (`complete_the_look.py`) — complementary,
     different-category items, using the catalog's `complementary_items`
     field as a candidate hint (not a final answer). Enforces **one
     suggestion per "outfit slot"**, and ranks suggestions by
     **priority_rank** (1 = most valuable) so budget-constrained scenarios
     keep the most important item first rather than an arbitrary one.
  3. **Similar Items** (`similar_items.py`) — other same-category
     alternatives at a comparable price, for browsing/variety. **Only used
     in Human-Browse mode** (see Purchase Architecture) — never
     auto-purchased in Fully-Autonomous mode, to avoid e.g. buying two
     t-shirts when the customer asked for one.
  4. **Cart-Value Threshold Nudge** (`cart_nudge.py`) — pure-arithmetic
     (no LLM) incentive message, e.g. "Add ₹150 more to unlock free
     delivery," using a configurable threshold from `policy.json`.
- **Catalog fixes made during testing:** expanded complementary-item
  candidates (1→3 per outfit-slot), added gender-aware selection (fixed
  many LLM rejections caused by nonsensical gender-mismatched hints), and
  reassigned synthetic ratings for 147 products that had no rating in the
  raw dataset (disclosed for transparency — not real customer data).

### Phase 4 — Policy Engine + Purchase Architecture ✅
- **`buyer-agent/policy_engine.py`** ties product-selection and all revenue
  modules into one coherent, bounded, auditable order-building flow
- **Two purchase modes**, resolving a real risk discovered during design
  (an agent autonomously adding items the customer never actually wanted):
  - **Fully-Autonomous mode**: the customer states a request and,
    optionally, opts into "Complete the Look" with a *separate* add-ons
    budget. True Upsell is bounded by the customer's own stated primary
    price ceiling (it's a *replacement*, not an addition, so needs no
    separate consent). Complete the Look is bounded by the opt-in add-ons
    budget. **Similar Items is not used here** — there's no human to
    choose between duplicate-risk alternatives.
  - **Human-Browse mode**: the agent surfaces all options (upsell,
    complete-the-look, similar items) for the human to choose from,
    without auto-applying any of them — no upfront budget needed here,
    since the human sees real prices and self-regulates. Once selected,
    the agent executes payment autonomously — same as the other mode.
  - **The common thread**: regardless of who chooses *what* to buy, the
    agent always handles *how* it gets bought (search, policy checks, the
    actual Razorpay transaction) — never a manual, human-clicked step.
- **Priority-ranked budget allocation**: when a customer's addons-budget
  can't fit every suggested item, the engine keeps items in the LLM's own
  priority order (not an arbitrary list-order) — verified via testing
  that showed the previous list-order approach was essentially
  coincidental, tied to slot-processing order rather than genuine
  importance.
- **Code-level safety nets throughout**: every module's LLM decision is
  re-verified in code (price, stock, budget, valid IDs) before being
  trusted — since testing surfaced real cases of LLM arithmetic mistakes
  (e.g. incorrectly concluding a ₹2,796 item exceeded a ₹5,000 budget).

### Phase 5 — Razorpay Integration ✅
- **`buyer-agent/razorpay_client.py`** — creates orders (`create_order()`),
  verifies payment signatures (`verify_payment_signature()`), and can
  capture/fetch payments.
- **Important correction made during development**: initially assumed
  Razorpay's server-side SDK could create a card payment directly with raw
  card numbers. This is incorrect — for PCI-DSS compliance, actual payment
  collection must go through Razorpay's Checkout UI (browser-based), even
  in test mode. The server side only creates orders and verifies/captures
  payments; a minimal standalone `test_checkout.html` (temporary — not the
  Phase 10 frontend) was built to complete test payments via Checkout.js
  ahead of the real frontend being built.
- **Correct test card discovered via Razorpay's official docs** (an
  earlier generic Visa test number triggered an "international cards not
  supported" error on an India test account): domestic Indian test card is
  **4100 2800 0000 1007** (any CVV, any future expiry, any 4+ digit OTP for
  success, <4 digits for a deliberate failure — useful for Phase 9).
- **Full loop verified end-to-end**: order created → real test payment
  completed via Checkout → signature verified server-side (`True`).
- **`policy_engine.py` now creates a real Razorpay order automatically**
  whenever a `build_order()` call resolves to `auto_approved` — the
  order's `notes` field carries the agent's `item_ids` and
  `reasoning_summary`, confirmed visible directly in the Razorpay
  dashboard. `pending_approval` and Browse-mode results deliberately do
  **not** create a Razorpay order yet — creating a real payable order
  before a human/merchant has approved it would defeat the point of the
  gate.

---

## Purchase Architecture: Two Modes

A key design decision made during Phase 3/4 testing: letting the agent
autonomously ADD extra items (cross-sell/similar-items) without any human
checkpoint risks charging a customer for something they never actually
wanted (e.g. two t-shirts when they asked for one). The fix separates
**who selects items** from **who executes payment** — the latter is
*always* the agent, in both modes below, preserving the PS's "no human
clicking buy" requirement for the actual transaction itself.

### Mode 1: Fully Autonomous
The customer states their request (e.g. "a t-shirt under ₹1000") and,
optionally, opts into "Complete the Look" with a separate add-ons budget
(e.g. "up to ₹500 more"). The agent then runs end-to-end with no further
human input:
- **True Upsell** operates only within the customer's own stated primary
  budget — a *replacement*, not an addition, so it doesn't need separate
  consent beyond the price ceiling the customer already gave.
- **Complete the Look** operates only within the separately-stated,
  opt-in add-ons budget, keeping the highest-priority items first if the
  budget can't fit everything the LLM suggested.
- **Similar Items is not used in this mode** — no human to choose between
  alternatives, so auto-adding one risks duplicate purchases.
- The agent creates the Razorpay order automatically if `auto_approved`;
  a high-value total instead sets `pending_approval` and no order is
  created until that's resolved.

### Mode 2: Human-Browse, Agent-Executes
The agent still searches and runs all four revenue mechanisms, but
presents them as **options for the human to choose from**, rather than
auto-applying any of them. No upfront budget question is needed — the
human sees real prices and self-regulates naturally. Once the human
finalizes their selection (which may legitimately include, say, two
t-shirts if they consciously pick both), the agent takes over and
executes the payment autonomously — same policy/gate/audit pipeline as
Mode 1.

**The common thread across both modes:** regardless of who chooses *what*
to buy, the agent always handles *how* it gets bought — search, policy
checks, and the actual Razorpay transaction are never a manual, human-
clicked step.

---

## Known Limitations / Scoping Decisions

Deliberately compared against real agentic-commerce concepts (ACP, AP2,
x402, NPCI UAP) to be explicit about what's simplified for buildathon
scope vs. what would need more work in a production system:

- **Authorization is a stored flag, not a cryptographic mandate.** Real
  protocols like AP2 use signed mandates to *prove* a payment was
  customer-authorized. Our consent/budget model captures the same
  *intent* but stores it as a simple record, not a cryptographically-
  verifiable proof.
- **Merchant-policy vs. customer-budget are separated**, after initially
  being conflated. `policy.json`'s spend-caps/approval-gate are
  *merchant-side* governance bounds; the customer's own stated budget
  (primary item price ceiling + optional add-ons budget) is a *separate*,
  per-purchase authorization layer.
- **Prompt-injection resistance is partially built, not yet explicitly
  tested.** Every revenue module already includes a code-level safety net
  that re-verifies price/stock/ID against the LLM's decision rather than
  trusting it blindly — this already defends against the *effect* of a
  crafted-malicious-description attack, but it hasn't been deliberately
  tested with one. Planned as a Phase 9 failure scenario.
- **Liability and returns are out of scope.** What happens if the agent
  buys the wrong size/color, and who's responsible, isn't modeled. The
  approval-gate on high-value orders indirectly reduces this risk.
- **Agent-to-agent trust/interoperability is not applicable.** This
  project is a single buyer-agent talking to a single merchant catalog —
  cross-company trust scenarios don't arise by design, not by oversight.
- **Payment collection requires a browser (Checkout UI), not pure
  server-to-server.** This is a Razorpay/PCI-DSS platform constraint, not
  a design choice — discovered during Phase 5 after an initial (incorrect)
  assumption that server-side card payments were possible. A minimal
  `test_checkout.html` bridges this until the Phase 10 frontend exists.

---

## Setup Instructions

### 1. Razorpay Test Account
1. Sign up / log in at https://dashboard.razorpay.com
2. Switch to **Test Mode** (toggle top-left of dashboard)
3. Go to **Settings → API Keys → Generate Key**
4. Copy `Key Id` and `Key Secret` into `.env`

### 2. Backend Setup
```bash
cd backend
python -m venv venv
venv\Scripts\activate      # on Mac/Linux: source venv/bin/activate
pip install -r requirements.txt
copy .env.example .env     # on Mac/Linux: cp .env.example .env
# fill in RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET, MISTRAL_API_KEY in .env
```

### 3. Generate the Catalog + Build Search Index
```bash
python scripts/generate_catalog.py
python ../catalog-service/build_embeddings.py
```

### 4. Run the Backend
```bash
python main.py
```
Visit http://localhost:8000/catalog and http://localhost:8000/policy to confirm.

### 5. Test the Full Policy + Payment Flow
```bash
python ../buyer-agent/policy_engine.py
```
For any `auto_approved` test result, a real Razorpay test-mode order is
created. To actually complete a test payment (since there's no frontend
yet), open `buyer-agent/test_checkout.html` in a browser, paste in the
`razorpay_order_id` / `razorpay_key_id` from the script's output, and pay
using Razorpay's official India test card:
- **Card:** 4100 2800 0000 1007
- **Expiry:** any future date · **CVV:** any random number
- **OTP (if asked):** any 4+ digit number for success, <4 digits to
  deliberately trigger a failure

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
descriptions). Cleaned to remove scraping artifacts (brand/store names
mistakenly captured as category — e.g. "BOLDFIT", "Milton", "RANDOM"),
leaving **897 genuine products across 53 real categories**.

Added or corrected manually since the raw dataset doesn't include it or
has gaps:

- **Stock quantities** — ~26 items deliberately set to 0. Out-of-stock
  items are excluded from search entirely; the Phase 9 failure-demo
  instead simulates a stock race-condition at payment time.
- **Gender-aware complementary-item mapping** — a category-group rule
  engine (e.g. tops ↔ accessories/bottoms/footwear) preferring
  same-gender candidates, with 3 candidates generated per outfit-slot so
  the agent's reasoning has genuine alternatives. This field is a
  **candidate hint**, not a final answer — the buyer agent decides
  relevance, style, and budget-fit, and explains that decision.
- **Ratings** — 147 of 897 products had no rating in the original dataset
  (0.0, meaning "no reviews yet"); reassigned a synthetic rating between
  3.5 and 4.8. **Disclosed here for transparency — not real customer
  data.** The remaining ~750 products carry genuine Myntra ratings.
- Each product carries a real `image_url` from Myntra's CDN. The dataset
  is from 2021-2022, so a few links may be dead — add an `onError`
  fallback in the frontend:

```jsx
<img
  src={product.image_url}
  alt={product.name}
  onError={(e) => { e.target.onerror = null; e.target.src = "/placeholder-product.png"; }}
/>
```

5 products naturally exceed the ₹10,000 approval-gate threshold, so
gate/approval scenarios trigger organically. Fully reproducible via
`backend/scripts/generate_catalog.py`.

---

## Project Structure

agentic-commerce/
├── backend/
│ ├── data/
│ │ ├── catalog.json # 897 real Myntra-sourced products
│ │ ├── policy.json # spend caps, gate thresholds, cart incentives, consent schema
│ │ ├── faiss_index.bin # FAISS semantic search index
│ │ └── faiss_id_map.json
│ ├── scripts/generate_catalog.py
│ ├── main.py
│ ├── requirements.txt
│ └── .env.example
├── catalog-service/
│ ├── build_embeddings.py
│ ├── bm25_search.py
│ ├── query_parser.py
│ └── hybrid_search.py
├── buyer-agent/
│ ├── reasoning_engine.py # core product-selection (Phase 3)
│ ├── upsell_true.py # same-category premium upgrade (Phase 3)
│ ├── complete_the_look.py # multi-item complementary suggestions, priority-ranked (Phase 3)
│ ├── similar_items.py # same-category alternatives (Phase 3)
│ ├── cart_nudge.py # cart-value threshold nudge (Phase 3)
│ ├── policy_engine.py # orchestrates everything + Razorpay + approval-gate (Phase 4/5)
│ ├── razorpay_client.py # order creation, signature verification (Phase 5)
│ └── test_checkout.html # temporary manual-test page (not the real frontend)
├── audit-service/ # logging + dashboard API (Phase 7)
└── frontend/ # React UI (Phase 10)
  

## Policy Summary (data/policy.json)
- Max spend per transaction: ₹20,000 (merchant-side bound)
- Approval gate triggers above: ₹10,000
- Free-delivery cart-nudge threshold: ₹1,999 (nudge shown if within 30% of it)
- Customer-side primary/add-ons budgets: enforced per-purchase in `policy_engine.py`

## Next Steps (Phase 6)
- Add a LinUCB (or Thompson Sampling) bandit to the product-selection step
- Design a reward signal (successful bounded purchase = positive reward)
- Test that the agent's choices measurably improve over simulated rounds  