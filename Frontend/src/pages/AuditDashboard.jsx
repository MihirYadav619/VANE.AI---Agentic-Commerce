import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";

const API_BASE = "http://localhost:8000";
const FALLBACK_IMAGE = "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='100' height='100'%3E%3Crect width='100' height='100' fill='%23e5e7eb'/%3E%3Ctext x='50' y='55' font-size='10' fill='%239CA3AF' text-anchor='middle'%3ENo Image%3C/text%3E%3C/svg%3E";

const DECISION_COLORS = {
  main_selection: "bg-blue-500/20 text-blue-300",
  true_upsell: "bg-purple-500/20 text-purple-300",
  complete_the_look: "bg-pink-500/20 text-pink-300",
  browse_options_generated: "bg-gray-500/20 text-gray-300",
  human_selection_finalized: "bg-teal-500/20 text-teal-300",
  cart_checkout: "bg-teal-500/20 text-teal-300",
  human_approval: "bg-orange-500/20 text-orange-300",
  merchant_promotion: "bg-yellow-500/20 text-yellow-300",
  failure_stock_out: "bg-red-500/20 text-red-300",
  failure_payment: "bg-red-500/20 text-red-300",
  failure_prompt_injection_test: "bg-red-500/20 text-red-300",
};

function ProductThumb({ src, alt, className }) {
  return (
    <img
      src={src || FALLBACK_IMAGE}
      alt={alt}
      className={className}
      onError={(e) => {
        e.target.onerror = null;
        e.target.src = FALLBACK_IMAGE;
      }}
    />
  );
}

// Same inline icon set used on the Shop page footer, so the audit page's
// footer matches exactly instead of drifting to different glyphs.
function LinkedInIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
      <path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433a2.062 2.062 0 1 1 0-4.124 2.062 2.062 0 0 1 0 4.124zM7.114 20.452H3.558V9h3.556v11.452z" />
    </svg>
  );
}

function GitHubIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
      <path d="M12 .5C5.73.5.98 5.24.98 11.52c0 4.94 3.2 9.13 7.65 10.61.56.1.76-.24.76-.54 0-.27-.01-1.16-.02-2.1-3.11.68-3.77-1.32-3.77-1.32-.51-1.29-1.24-1.63-1.24-1.63-1.01-.69.08-.68.08-.68 1.12.08 1.71 1.15 1.71 1.15 1 1.71 2.62 1.22 3.26.93.1-.72.39-1.22.71-1.5-2.49-.28-5.1-1.24-5.1-5.53 0-1.22.44-2.22 1.15-3-.12-.28-.5-1.42.11-2.96 0 0 .93-.3 3.05 1.15a10.6 10.6 0 0 1 5.56 0c2.12-1.45 3.05-1.15 3.05-1.15.61 1.54.23 2.68.11 2.96.72.78 1.15 1.78 1.15 3 0 4.3-2.62 5.24-5.12 5.52.4.35.76 1.03.76 2.08 0 1.5-.01 2.71-.01 3.08 0 .3.2.65.77.54A11.03 11.03 0 0 0 23.02 11.5C23.02 5.24 18.27.5 12 .5z" />
    </svg>
  );
}

export default function AuditDashboard() {
  const navigate = useNavigate();
  const [decisions, setDecisions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [productCache, setProductCache] = useState({}); // id -> { image_url, name }

  const fetchAudit = () => {
    setLoading(true);
    fetch(`${API_BASE}/audit/recent?limit=30`)
      .then((res) => res.json())
      .then(async (data) => {
        setDecisions(data);
        await enrichProducts(data);
      })
      .catch(() => setDecisions([]))
      .finally(() => setLoading(false));
  };

  // Collect every distinct first-product-id referenced across all decisions
  // and fetch each one only once, caching the result by id.
  const enrichProducts = async (data) => {
    const idsToFetch = new Set();
    data.forEach((d) => {
      const productIds = typeof d.product_ids === "string" ? JSON.parse(d.product_ids) : d.product_ids;
      const firstId = Array.isArray(productIds) ? productIds[0] : null;
      if (firstId) idsToFetch.add(firstId);
    });

    const newEntries = {};
    await Promise.all(
      Array.from(idsToFetch).map(async (id) => {
        if (productCache[id]) return;
        try {
          const res = await fetch(`${API_BASE}/catalog/product/${id}`);
          if (!res.ok) return;
          const product = await res.json();
          newEntries[id] = { image_url: product.image_url, name: product.name };
        } catch {
          // leave unset — thumbnail falls back to placeholder
        }
      })
    );

    if (Object.keys(newEntries).length > 0) {
      setProductCache((prev) => ({ ...prev, ...newEntries }));
    }
  };

  useEffect(() => {
    fetchAudit();
  }, []);

  return (
    <div className="relative h-screen overflow-hidden flex flex-col bg-black text-white">
      {/*
        Background image — drop your file in Frontend/public/ (e.g. audit-bg.png)
        and reference it by absolute path below. No import needed since it's
        served straight from the site root.
      */}
      <div
        className="absolute inset-0 bg-cover bg-center opacity-20 pointer-events-none"
        style={{ backgroundImage: "url(/audit-bg.png)" }}
      />

      {/* ============ NAVBAR (matches Shop.jsx — flat, pink accent, no border) ============ */}
      <div className="relative flex justify-between items-center px-8 py-4 flex-shrink-0">
        <h1 className="text-lg font-semibold tracking-[0.3em] text-pink-500">VANE.AI</h1>
        <div className="flex items-center gap-3 text-[11px] font-bold tracking-wider uppercase">
          <button
            onClick={fetchAudit}
            className="border border-white/20 text-white/70 hover:text-white hover:border-white/40 transition-colors px-4 py-2 rounded-md"
          >
            ↻ Refresh
          </button>
          <button
            onClick={() => navigate("/shop")}
            className="border border-pink-500 text-pink-400 hover:bg-pink-500 hover:text-white transition-colors px-4 py-2 rounded-md"
          >
            ← Back to Shop
          </button>
        </div>
      </div>

      {/* ============ HEADER (fixed height, does not scroll) — enlarged ============ */}
      <div className="relative max-w-6xl mx-auto w-full px-8 pt-6 pb-6 flex-shrink-0">
        <p className="text-pink-500 text-sm font-bold tracking-[0.4em] uppercase mb-4">
          Audit Trail
        </p>
        <h2 className="font-serif text-5xl md:text-6xl leading-tight mb-4">
          Every decision <span className="text-pink-500 italic">Vane</span> makes.
        </h2>
        <p className="text-white/70 text-base max-w-3xl">
          Every decision the buyer-agent and merchant-agent have made — reasoning, outcomes, and metadata, fully traceable.
        </p>
      </div>

      {/* ============ DECISIONS LIST — the ONLY scrollable region, enlarged ============ */}
      <div className="relative flex-1 min-h-0 overflow-y-auto">
        <div className="max-w-6xl mx-auto px-8 pb-8">
          {loading ? (
            <p className="text-white/40 text-base">Loading audit trail...</p>
          ) : decisions.length === 0 ? (
            <p className="text-white/40 text-base">No decisions logged yet. Go shop for something!</p>
          ) : (
            <div className="space-y-4">
              {decisions.map((d) => {
                const metadata = typeof d.metadata === "string" ? JSON.parse(d.metadata) : d.metadata;
                const productIds = typeof d.product_ids === "string" ? JSON.parse(d.product_ids) : d.product_ids;
                const firstId = Array.isArray(productIds) ? productIds[0] : null;
                const product = firstId ? productCache[firstId] : null;

                return (
                  <div key={d.id} className="bg-white/5 border border-white/10 rounded-2xl p-6 hover:border-white/20 transition-colors">
                    <div className="flex gap-5">
                      {firstId && (
                        <ProductThumb
                          src={product?.image_url}
                          alt={product?.name || "product"}
                          className="w-20 h-20 rounded-xl object-cover flex-shrink-0 bg-white/10"
                        />
                      )}
                      <div className="flex-1 min-w-0">
                        <div className="flex justify-between items-start mb-3">
                          <span
                            className={`text-xs font-bold uppercase tracking-wide px-3 py-1.5 rounded-full ${
                              DECISION_COLORS[d.decision_type] || "bg-white/10 text-white/70"
                            }`}
                          >
                            {d.decision_type.replace(/_/g, " ")}
                          </span>
                          <span className="text-sm text-white/40 whitespace-nowrap ml-3">
                            {new Date(d.timestamp).toLocaleString()}
                          </span>
                        </div>
                        <p className="text-base text-white/85 mb-3 leading-relaxed">{d.reasoning}</p>
                        {productIds?.length > 0 && (
                          <p className="text-sm text-white/50 mb-1">
                            {product?.name ? `${product.name} · ` : ""}Products: {productIds.join(", ")}
                          </p>
                        )}
                        {metadata?.bandit_applied !== undefined && (
                          <p className="text-sm text-white/50">
                            Bandit applied: {metadata.bandit_applied ? "Yes" : "No"}
                            {metadata.bandit_status && ` (${metadata.bandit_status})`}
                          </p>
                        )}
                        <p className="text-xs text-white/25 mt-3">Session: {d.session_id}</p>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>

      {/* ============ FOOTER — pinned, always visible, never needs scrolling ============ */}
      <div className="relative px-8 py-4 flex flex-col sm:flex-row justify-between items-center gap-2 text-[11px] text-white/40 text-center sm:text-left border-t border-white/10 flex-shrink-0 bg-black">
        <p>
          <span className="text-pink-500">"Great style starts with trust."</span>
          <br className="sm:hidden" /> VANE shops. You look good.
        </p>
        <div className="flex items-center gap-6 uppercase tracking-wider">
          <a href="#" className="hover:text-white transition-colors">About</a>
          <a href="#" className="hover:text-white transition-colors">Privacy</a>
          <a href="#" className="hover:text-white transition-colors">Terms</a>
          <a href="#" className="hover:text-white transition-colors">Help</a>
          <div className="flex items-center gap-3 text-pink-500 normal-case">
            <a
              href="https://www.linkedin.com/in/mihir-yadav-4509aa315/"
              target="_blank"
              rel="noopener noreferrer"
              aria-label="LinkedIn"
              className="hover:text-pink-400 transition-colors"
            >
              <LinkedInIcon />
            </a>
            <a
              href="https://github.com/MihirYadav619/Agentic-Commerce"
              target="_blank"
              rel="noopener noreferrer"
              aria-label="GitHub"
              className="hover:text-pink-400 transition-colors"
            >
              <GitHubIcon />
            </a>
          </div>
        </div>
      </div>
    </div>
  );
}