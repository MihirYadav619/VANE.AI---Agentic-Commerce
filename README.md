# Agentic Commerce — Razorpay Buildathon (Track 01: AI Growth & Agentic Commerce)

An AI buyer agent that autonomously shops a merchant's catalog and completes
payments via Razorpay test-mode APIs — with every money action explainable,
bounded, gated, and audited. A second, independent merchant-side agent
makes this a genuine multi-agent system, not just a single bot.

---

## Project Goals

### Core Goals
- [x] Agent-readable catalog (897 products, machine-queryable)
- [x] Hybrid retrieval (FAISS + BM25 + RRF)
- [x] AI buyer agent with explainable, honest reasoning
- [x] Purchase execution end-to-end (Razorpay Orders + Checkout + signature verification)
- [x] Multiple revenue-growth mechanisms (Upsell, Complete-the-Look, Similar Items, Cart-Nudge)
- [x] Policy/guardrail engine (customer-budgets + merchant-side caps)
- [x] Approval gate (order-total-based)
- [x] Real Razorpay test-mode integration
- [x] **Audit trail** — SQLite-backed, every decision + transaction logged and queryable
- [ ] At least one graceful failure (Phase 9)

### Additional Goals
- [x] **Bandit algorithm (LinUCB)** — see Phase 6, including a real
      cold-start safety-mechanism discovered and fixed during testing.
- [ ] Multiple failure scenarios (5, not just 1) — including
      **prompt-injection resistance** (Phase 9).
- [ ] Measured retrieval quality metric.
- [x] **Second agent for a true multi-agent demo** — see Phase 7/8 below.
      A genuinely independent merchant-side agent, communicating with the
      buyer-agent through a shared, auditable signal.
5. UI/UX deep polish (Phase 10).

**Checkpoint (completed after Phase 5):** On-time. Proceeding with the
full additional-goals list.

---

## Progress Log

*(Phases 1-6 unchanged from previous version — see prior sections: real
Myntra catalog, hybrid retrieval with RRF, four revenue mechanisms,
policy engine with two purchase modes, Razorpay integration, and the
LinUCB bandit with its cold-start safety-mechanism fix.)*

### Phase 7 — Audit Trail + Merchant-Agent Foundation ✅

**Audit Trail** (`audit-service/audit_db.py`): SQLite database with two
tables — `decisions` (every reasoning-step: main selection, true upsell,
complete-the-look, merchant promotions) and `transactions` (final order
outcomes) — grouped by a per-purchase `session_id` so a complete decision
history can be traced for any transaction. This is what makes the system
genuinely auditable, not just "explainable in the moment" via a printed
string that disappears when the script exits.

**Merchant-Agent** (`merchant-agent/merchant_agent.py`) — the system's
**second, independent agent**, directly addressing the "Agentic" half of
the track name (most teams build only a single buyer-bot). It thinks from
the *merchant's* side:
- Reads real demand signal directly from the audit trail (`SELECT
  item_ids FROM transactions WHERE status = 'auto_approved'`, counted per
  category over the last 20 transactions) — no fabricated data.
- Decides bounded promotions via a deterministic rule (not an LLM): a
  category needs ≥3 recent purchases to be "trending", and the discount
  scales with demand but is hard-capped at 10% — this makes the "bounded"
  claim easy to defend, since there's no LLM-hallucination risk in the
  discount math itself.
- Publishes decisions to a shared file (`active_promotions.json`) — a
  deliberately simple communication mechanism between the two agents,
  rather than a complex message-passing protocol.

**Buyer-agent integration**: `reasoning_engine.py` now checks
`get_active_promotions()` before reasoning, and includes any promotion
relevant to the candidate categories in its LLM prompt — the LLM is
explicitly instructed that match-quality comes first and a promotion must
never cause it to pick a worse-fitting candidate.

**Verified end-to-end**: a "watch" query correctly showed
`active_promotions_seen: {}` (a "Shirts" promotion was active but
correctly filtered out as irrelevant to watches), while a "shirt" query
correctly surfaced and mentioned the active discount — confirming the
category-filtering is genuinely selective, not a blanket application.

### Phase 8 — Second Agent (Merchant-Side) Complete ✅

Closed the loop so the two agents interact **fully autonomously**, with
no manual script-running required:
- `merchant_agent.py`'s own decisions (new/changed/removed promotions)
  are now also logged to the shared audit trail
  (`decision_type: "merchant_promotion"`), only for categories where the
  promotion actually *changed* — avoiding redundant no-op log spam.
- `policy_engine.py` automatically calls `run_merchant_agent()` after
  every `auto_approved` transaction — the merchant-agent re-evaluates
  demand and updates its promotions in the same run, without any human
  intervention.

**Verified in a single run**: one `policy_engine.py` execution showed the
buyer-agent consuming an existing 6% "Shirts" promotion in its reasoning,
completing a purchase, and then — automatically, in the same run — the
merchant-agent recalculating demand (now 6 purchases) and updating the
promotion to 8%, all traceable in one `session_id`'s audit history. This
is a genuine, verified multi-agent interaction loop: two independently-
reasoning agents, coupled only through a shared auditable signal, not a
hardcoded call between them.

**Demo note**: the bandit algorithm (Phase 6) will be described in the
pitch/Q&A rather than shown live (it only meaningfully activates after
5+ real purchases per category, which the demo won't organically
generate). The merchant-agent loop, by contrast, **is** demo-able live,
since its threshold (3 purchases) is achievable within a short live demo.

---

## Purchase Architecture: Two Modes

*(unchanged — see Mode 1: Fully Autonomous and Mode 2: Human-Browse,
Agent-Executes in the previous version)*

---

## Known Limitations / Scoping Decisions

*(unchanged, plus:)*
- **The bandit only refines main-product selection**, not the three
  revenue-add-on mechanisms — a deliberate scoping decision (see Phase 6),
  not an oversight.
- **The merchant-agent's demand signal is simple recency-based counting**,
  not sophisticated time-series forecasting — appropriate for buildathon
  scope; a production system would likely use more advanced trend-detection.
- **Merchant-agent promotions apply store-wide** (any customer sees the
  same active discount for a trending category) — no per-customer
  personalization, which is out of scope here.

---

## Setup Instructions

### 1. Razorpay Test Account
Sign up at https://dashboard.razorpay.com, switch to **Test Mode**,
generate API keys under **Settings → API Keys**, add to `.env`.

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

### 4. Run the Full System (Buyer-Agent + Policy + Razorpay + Bandit + Audit + Merchant-Agent)
```bash
python ../buyer-agent/policy_engine.py
```
A single run: selects a product, checks/applies bounded revenue
mechanisms, creates a real Razorpay order if auto-approved, feeds the
bandit, logs everything to the audit trail, and triggers the
merchant-agent's demand re-evaluation — all in one autonomous flow.

To complete an actual test payment, open `buyer-agent/test_checkout.html`
with the printed `razorpay_order_id` / `razorpay_key_id`, and pay with
Razorpay's India test card: **4100 2800 0000 1007**, any future expiry,
any CVV.

### 5. Inspect the Audit Trail Directly
```bash
python ../audit-service/audit_db.py
```

### 6. Run the Merchant-Agent Standalone (Optional — normally auto-triggered)
```bash
python ../merchant-agent/merchant_agent.py
```

### 7. Frontend Setup (Phase 10, not needed yet)
```bash
cd frontend
npm create vite@latest . -- --template react
npm install
npm install -D tailwindcss postcss autoprefixer
```

---

## Catalog Source

*(unchanged — real Myntra dataset, 897 products, 53 categories,
gender-aware complementary mapping, synthetic ratings for 147 products
disclosed for transparency.)*

---

## Project Structure
agentic-commerce/
├── backend/
│ ├── data/
│ │ ├── catalog.json
│ │ ├── policy.json
│ │ ├── faiss_index.bin
│ │ ├── faiss_id_map.json
│ │ ├── bandit_state.json # LinUCB learned state (Phase 6)
│ │ ├── audit.db # SQLite audit trail (Phase 7)
│ │ └── active_promotions.json # merchant-agent's published promotions (Phase 7/8)
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
│ ├── reasoning_engine.py # core selection + bandit + promotion-awareness
│ ├── bandit.py # LinUCB contextual bandit
│ ├── upsell_true.py
│ ├── complete_the_look.py
│ ├── similar_items.py
│ ├── cart_nudge.py
│ ├── policy_engine.py # orchestrates everything + Razorpay + audit + merchant-agent trigger
│ ├── razorpay_client.py
│ └── test_checkout.html
├── merchant-agent/
│ └── merchant_agent.py # SECOND agent — demand-detection + bounded promotions (Phase 7/8)
├── audit-service/
│ └── audit_db.py # SQLite schema + logging functions (Phase 7)
└── frontend/ # React UI (Phase 10)


## Policy Summary (data/policy.json)
- Max spend per transaction: ₹20,000 (merchant-side bound)
- Approval gate triggers above: ₹10,000
- Free-delivery cart-nudge threshold: ₹1,999
- Bandit minimum-observations-to-override: 5 per category
- Merchant-agent: max discount 10%, trending-threshold 3 purchases per 20-transaction window

## Next Steps (Phase 9)
- Build 5 distinct failure scenarios: payment timeout, stock-out
  (race-condition), policy violation, API rate-limit, and
  prompt-injection resistance
- Each with its own graceful recovery flow (retry/rollback/notify/escalate)
- All failures logged to the same audit trail with full reasoning