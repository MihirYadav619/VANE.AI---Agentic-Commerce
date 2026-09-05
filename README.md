# Vane.ai — Agentic Commerce

**An agent that shops — on your terms. And a merchant that grows its own revenue — on its own.**

Vane.ai is a full-stack agentic commerce platform: an AI buyer-agent that can autonomously discover, decide, and purchase on a merchant's catalog end to end, and an independent merchant-agent that grows revenue by reacting to real demand — all running on Razorpay's payment infrastructure, with every money-moving action explainable, bounded, and gated.

---

## Design principle: every money action is explainable, bounded, and gated

This is the core constraint the entire system is built around, not an afterthought:

- **Explainable** — every decision the buyer-agent or merchant-agent makes is logged with a plain-language reasoning string, not just a status code. Visible in both a customer-facing Audit Trail and a Merchant Dashboard.
- **Bounded** — a policy file enforces a max spend per transaction, a max upsell-addon percentage, a daily agent spend cap, and per-category price restrictions. The agent cannot exceed these regardless of what it decides it wants to buy.
- **Gated** — any order above a configurable approval threshold pauses and requires explicit human approval before a payment is ever charged. Autonomy has a hard ceiling.
- **Fails gracefully** — the agent will honestly return "no genuine match found" rather than force a bad purchase, and an over-budget order degrades to a pending-approval state instead of silently overspending.

---

## Core Features

### Shopping Modes
- **Autonomous Mode** — describe what you want in plain language; the agent searches, decides, and completes the purchase end-to-end. Optional "Complete the Look" builds a full outfit within a stated add-ons budget.
- **Browse Mode** — search as many times as you like, review the agent's recommendations side by side, build a cart across multiple searches, and checkout once.

### Buyer-Agent Pipeline
- **Hybrid search** over the product catalog to retrieve relevant candidates — a genuinely agent-readable catalog layer, not a page meant only for human browsing.
- **LLM-based reasoning** that separates *hard constraints* (category, stated color, stated brand) from *soft preferences* (comfortable, stylish, professional) — rejecting a candidate only on a real violation, never on an assumption the user never actually stated.
- **True Upsell** — suggests a same-category upgrade only when it's a meaningfully better product, not just a pricier one.
- **Complete the Look** — suggests at most one complementary item per outfit slot (topwear, footwear, accessory, etc.), ranked by priority, respecting the customer's stated budget.
- **Similar Items** — surfaces genuinely different same-category alternatives (never near-duplicates) at a comparable price point.
- **Cart-value nudge** — a lightweight, LLM-free calculation that only nudges toward a free-delivery threshold when the remaining gap is realistically closeable.
- **LinUCB contextual bandit** — refines final product selection within a category once that category has accumulated enough real purchase history to have a genuinely learned preference, avoiding cold-start noise.

### Merchant-Agent — independent revenue growth
- Runs automatically after every completed transaction, monitoring recent purchase volume per category and adjusting promotional discounts in response to real demand trends.
- Fully independent from the buyer-agent's own decision process — the two coordinate only through a shared, auditable signal (the buyer-agent reads and reasons over live promotions when deciding what to recommend), not a hardcoded coupling between them.
- Live and visible in the Merchant Dashboard's Promotions tab, with the reasoning behind every adjustment.

### Trust & Safety
- **Spend-based approval gate** (configurable threshold) — orders above it require explicit human approval before payment.
- **Full audit trail** — every decision, transaction, and promotion update logged with reasoning, timestamps, and session grouping.
- **Code-level safety nets on top of every LLM decision** — e.g. verifying an LLM-suggested product ID actually exists among valid candidates, enforcing "one item per outfit slot" in code even if the model's own reasoning slips, capping suggestion counts, validating price sanity before ever showing a suggestion to a customer.

### Payments
- Real Razorpay Checkout integration (test mode) — order creation, payment-signature verification, capture.

### Two Dashboards
- **Customer Audit Trail** — a customer's view of what the agent decided and why.
- **Merchant Dashboard** — overview stats, live active promotions, and the full decision audit trail, behind a separate merchant login.

---

## Tech Stack

**Backend**
- FastAPI (Python) — REST API
- SQLite — auth (users/sessions), audit trail (decisions/transactions)
- Groq API (`openai/gpt-oss-120b` / `openai/gpt-oss-20b`) — structured tool-calling for product selection, upsell, complete-the-look, and similar-items decisions
- Razorpay Python SDK (test mode) — order creation and payment verification
- bcrypt — password hashing

**Frontend**
- React + Vite
- React Router
- Tailwind CSS
- Razorpay Checkout.js — browser-side payment UI

---

## Project Structure

Agentic Commerce/
├── Backend/
│ ├── main.py # FastAPI app — all HTTP endpoints
│ ├── auth.py # User signup/login/session management
│ └── data/
│ ├── catalog.json # Product catalog
│ ├── policy.json # Spend limits, approval threshold, cart incentives
│ └── users.db # SQLite (gitignored)
│
├── buyer-agent/
│ ├── reasoning_engine.py # Core product-selection reasoning (BuyerAgent)
│ ├── policy_engine.py # Orchestrates the full order pipeline + approval gate
│ ├── upsell_true.py # "True upsell" upgrade suggestions
│ ├── complete_the_look.py # Multi-item complementary suggestions
│ ├── similar_items.py # Same-category alternatives
│ ├── cart_nudge.py # Free-delivery threshold nudge
│ ├── bandit.py # LinUCB contextual bandit
│ └── razorpay_client.py # Razorpay order/payment integration
│
├── catalog-service/
│ └── hybrid_search.py # Product retrieval — agent-readable catalog layer
│
├── audit-service/
│ └── audit_db.py # Decision + transaction logging
│
├── merchant-agent/
│ └── merchant_agent.py # Independent revenue/promotion-adjustment agent
│
└── Frontend/
├── public/ # Images, videos, background assets
└── src/
├── pages/
│ ├── Landing.jsx
│ ├── Login.jsx / Signup.jsx
│ ├── ModeSelection.jsx
│ ├── Shop.jsx # Autonomous + Browse shopping UI
│ ├── AuditDashboard.jsx # Customer-facing audit trail
│ ├── MerchantLogin.jsx
│ └── MerchantDashboard.jsx # Merchant overview + promotions + audit
├── components/
│ ├── ProtectedRoute.jsx
│ └── MerchantProtectedRoute.jsx
├── api/auth.js
└── App.jsx


---

## Setup

### Prerequisites
- Python 3.10+
- Node.js 18+
- A [Groq API key](https://console.groq.com/keys) (free tier)
- A [Razorpay](https://razorpay.com) test-mode account (Key ID + Key Secret)

### Backend

```bash
cd Backend
python -m venv ../venv
../venv/Scripts/activate      # Windows
# source ../venv/bin/activate  # macOS/Linux

pip install -r requirements.txt
```

Create a `.env` file in `Backend/`:

GROQ_API_KEY=your_groq_key_here
RAZORPAY_KEY_ID=your_razorpay_key_id
RAZORPAY_KEY_SECRET=your_razorpay_key_secret


Run the backend:
```bash
python main.py
```
API available at `http://localhost:8000`.

### Frontend

```bash
cd Frontend
npm install
npm run dev
```
App available at `http://localhost:5173`.

---

## Usage

1. **Customers**: sign up at `/signup`, choose Autonomous or Browse mode, and start shopping.
2. **Merchant**: navigate to `/merchant-login` (linked from the landing page nav) — single shared password, since this represents one merchant managing their own catalog.
3. **Audit trail**: accessible from the shop page (`AUDIT` in the nav) for customers, and as a full tab in the Merchant Dashboard.

---

## Configuration

Spend limits, the approval-gate threshold, and cart-incentive rules are all controlled from `Backend/data/policy.json` — no code changes needed to adjust:
- `approval_gate.approval_required_above` — orders above this amount require manual approval.
- `spend_limits.max_spend_per_transaction`, `daily_agent_spend_cap`, `max_upsell_addon_percentage`
- `category_restrictions.restricted_categories` — per-category price caps
- `cart_incentives.free_delivery_threshold`, `nudge_trigger_max_gap_percentage`

---

## A quick walkthrough to see the full loop

1. Run an Autonomous-mode search **under** the approval threshold — watch it complete end-to-end, then open the Audit Trail to see the exact reasoning behind the pick.
2. Run one **over** the threshold — it pauses and asks for approval instead of charging automatically.
3. Run a deliberately unmatchable query — it returns an honest "no genuine match found" instead of forcing a purchase.
4. Open the Merchant Dashboard's Promotions tab — see a live, demand-reactive discount the merchant-agent set on its own, with the reasoning behind it.

---

## Author

**Mihir Yadav**
- LinkedIn: [linkedin.com/in/mihir-yadav-4509aa315](https://www.linkedin.com/in/mihir-yadav-4509aa315/)
- GitHub: [github.com/MihirYadav619/Agentic-Commerce](https://github.com/MihirYadav619/Agentic-Commerce)

---

## License

This project is provided as-is for educational and portfolio purposes.