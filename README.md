## Project Goals

### Core Goals (directly required by the problem statement)
- [ ] **Agent-readable catalog** exposing products in a machine-queryable format
- [ ] **AI buyer agent** that understands intent, searches the catalog, and
      completes a purchase end-to-end with no human clicking "buy"
- [ ] **Multi-step reasoning** — every decision is explainable, not a black box
- [ ] **Upsell/cross-sell step** — the agent also grows revenue within a
      transaction (the "grow the merchant's revenue" half of the PS)
- [ ] **Policy/guardrail engine** — every money action stays bounded
      (spend caps, category limits)
- [ ] **Approval gate** — high-value or policy-violating orders pause for
      approval instead of executing blindly
- [ ] **Real Razorpay test-mode integration** — Orders + Payments API,
      not a mocked/simulated payment
- [ ] **Audit trail** — every decision, reasoning, and transaction is logged
      and viewable in a dashboard
- [ ] **At least one graceful failure** — a deliberate failure scenario that
      the system recovers from without crashing or double-charging

### Additional Goals (planned as part of this build, executed after core
goals are stable — this is a sequencing order, not a priority cut list)
1. **Bandit algorithm (LinUCB / Thompson Sampling)** in the product-selection
   step — a genuinely defensible ML component for the buyer agent's
   decision-making, giving a strong answer if judges probe the technical
   depth. Requires designing a reward signal (successful bounded purchase =
   positive reward).
2. **Multiple failure scenarios (3-4, not just 1)** — payment timeout,
   stock-out, policy violation, and API rate-limit, each handled
   *differently* (retry / rollback / notify / escalate). Every recovery
   gets logged to the audit trail with reasoning, same as a normal decision.
3. **Bigger catalog + measured retrieval quality** — quantify hybrid search
   (FAISS + BM25) vs. keyword-only search with a simple metric (e.g.
   precision@k), so the retrieval-quality claim is backed by a number
   instead of just a demo.
4. **Second agent for a true multi-agent demo** — a merchant-side agent that
   adjusts pricing/promotions based on demand signals, interacting with the
   buyer agent (e.g. "demand rising in category X" → merchant agent reacts).
   Turns this from a single-agent system into a genuine multi-agent one.
5. **UI/UX deep polish** — live reasoning/typing effect on the dashboard,
   proper charts for revenue/approval/failure-recovery stats, mobile
   responsiveness.

## Phase 1 — What We Achieved

**Goal:** Set up the project foundation — folder structure, backend
skeleton, and a real, validated product catalog to build the buyer agent
against in later phases.

### 1. Project Structure
Created the full folder skeleton so every later phase has a home:
`backend/` (with `data/`, `routes/`, `models/`, `scripts/` subfolders),
`frontend/`, `catalog-service/`, `buyer-agent/`, `audit-service/`.

### 2. Backend Skeleton
Built a working FastAPI app (`backend/main.py`) with three endpoints:
- `GET /catalog` — returns the full product catalog
- `GET /catalog/product/{id}` — returns a single product by ID
- `GET /policy` — returns the current bounds/gate policy

This confirms the backend can serve data correctly before any agent logic
is added on top of it.

### 3. Real Product Catalog (897 products)
Originally planned as a small, hand-crafted 30-45 item catalog, but
switched to a **real dataset** for credibility and scale:

- Sourced ~1000 real Myntra (Indian fashion e-commerce) products from a
  public GitHub-hosted dataset sample, with genuine INR pricing, ratings,
  descriptions, and images
- Cleaned out scraping artifacts — some rows had brand/store names
  mistakenly captured as the "category" (e.g. "BOLDFIT", "Milton",
  "RANDOM") — leaving **897 genuine products across 53 real categories**
- Added data the raw dataset didn't include:
  - **Stock quantities**, with 26 products deliberately set to 0 for the
    Phase 9 failure-handling demo
  - **Complementary-item mapping** via a category-group rule engine (e.g.
    tops ↔ accessories, footwear ↔ bottoms) — designed as a *candidate
    hint* for the buyer agent, not a final decision, since deciding
    whether to actually offer an upsell is the agent's job, not the
    catalog's
- Fixed two data-quality issues found during validation:
  - 147 products had a 0.0 rating (dataset shorthand for "no reviews
    yet") — reassigned a synthetic realistic rating (3.5–4.8) so the
    demo never surfaces an unrealistic 0-star recommendation. **Disclosed
    as synthetic, not real customer data.**
  - 237 products (mostly Watches and Wallets, the two largest categories)
    had no valid complementary-item pairing due to a gap in the grouping
    rules — fixed so only 1 genuine edge case (a baby-care item with no
    sensible fashion pairing) remains without one
- Final validation: 0 duplicate IDs, 0 broken complementary references,
  0 missing fields across all 897 products, 5 products naturally above
  the ₹10,000 approval-gate threshold, 26 out of stock

### 4. Policy & Config Files
- `backend/data/policy.json` — spend caps (₹20,000/transaction), the
  approval-gate threshold (₹10,000), and upsell rules (max 1 item, capped
  at 25% of order value)
- `backend/requirements.txt`, `.env.example`, `.gitignore` — so the
  project is reproducible and secrets are never committed

### 5. Reproducibility
Everything above is reproducible from a single script
(`backend/scripts/generate_catalog.py`) — anyone on the team can regenerate
the exact same catalog from scratch by running one command, rather than
depending on a static file being passed around.

### What's Deliberately Not Done Yet
No search/retrieval, no agent reasoning, no Razorpay calls, no audit
logging, no frontend — Phase 1 is purely the data + backend foundation
that Phase 2 onward builds on top of.
