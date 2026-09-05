import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";

const API_BASE = "http://localhost:8000";

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
};

export default function MerchantDashboard() {
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState("dashboard");
  const [decisions, setDecisions] = useState([]);
  const [transactions, setTransactions] = useState([]);
  const [promotions, setPromotions] = useState({});
  const [loading, setLoading] = useState(true);

  const fetchAll = () => {
    setLoading(true);
    Promise.all([
      fetch(`${API_BASE}/audit/recent?limit=50`).then((r) => r.json()).catch(() => []),
      fetch(`${API_BASE}/audit/recent-orders?limit=50`).then((r) => r.json()).catch(() => []),
      fetch(`${API_BASE}/merchant/promotions`).then((r) => r.json()).catch(() => ({})),
    ]).then(([d, t, p]) => {
      setDecisions(Array.isArray(d) ? d : []);
      setTransactions(Array.isArray(t) ? t : []);
      setPromotions(p || {});
      setLoading(false);
    });
  };

  useEffect(() => {
    fetchAll();
  }, []);

  const handleLogout = () => {
    localStorage.removeItem("merchant_authenticated");
    navigate("/merchant-login");
  };

  // Real, derivable numbers only — no invented "Unique Users"/"Security
  // Events" stats, since the project doesn't track those.
  const totalEvents = decisions.length;
  const totalTransactions = transactions.length;
  const autoApprovedCount = transactions.filter((t) => t.status === "auto_approved" || t.status === "approved_and_completed").length;
  const promotionCount = Object.keys(promotions).length;

  const navItems = [
    { id: "dashboard", label: "Dashboard" },
    { id: "promotions", label: "Promotions" },
    { id: "audit", label: "Audit Trail" },
  ];

  return (
    <div className="min-h-screen bg-black text-white flex">
      <div
        className="fixed inset-0 bg-cover bg-center opacity-20 pointer-events-none"
        style={{ backgroundImage: "url(/audit-bg.png)" }}
      />

      {/* ============ SIDEBAR ============ */}
      <div className="relative w-64 flex-shrink-0 border-r border-white/10 flex flex-col p-6">
        <h1 className="font-serif italic text-xl text-pink-500 mb-1">vane.ai</h1>
        <p className="text-white/40 text-[10px] tracking-widest uppercase mb-8">Fashion Brand</p>

        <nav className="flex-1 space-y-1">
          {navItems.map((item) => (
            <button
              key={item.id}
              onClick={() => setActiveTab(item.id)}
              className={`w-full text-left px-4 py-2.5 rounded-lg text-sm transition-colors ${
                activeTab === item.id
                  ? "bg-pink-500/15 text-pink-400 font-semibold"
                  : "text-white/60 hover:text-white hover:bg-white/5"
              }`}
            >
              {item.label}
            </button>
          ))}
        </nav>

        <button
          onClick={handleLogout}
          className="text-left px-4 py-2.5 rounded-lg text-sm text-white/60 hover:text-white hover:bg-white/5 transition-colors"
        >
          Log out
        </button>
      </div>

      {/* ============ MAIN CONTENT ============ */}
      <div className="relative flex-1 flex flex-col min-w-0">
        <div className="flex justify-between items-center px-8 py-6 border-b border-white/10">
          <div>
            <p className="text-pink-500 text-xs font-bold tracking-[0.35em] uppercase mb-2">
              Merchant Dashboard
            </p>
            <h2 className="font-serif text-3xl">
              {activeTab === "dashboard" && "Overview"}
              {activeTab === "promotions" && "Active Promotions"}
              {activeTab === "audit" && (
                <>
                  Every decision <span className="text-pink-500 italic">Vane</span> makes.
                </>
              )}
            </h2>
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={fetchAll}
              className="border border-white/20 text-white/70 hover:text-white hover:border-white/40 transition-colors px-4 py-2 rounded-md text-[11px] font-bold uppercase tracking-wider"
            >
              ↻ Refresh
            </button>
            <button
              onClick={() => navigate("/")}
              className="border border-pink-500 text-pink-400 hover:bg-pink-500 hover:text-white transition-colors px-4 py-2 rounded-md text-[11px] font-bold uppercase tracking-wider"
            >
              ← Exit
            </button>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto px-8 py-6">
          {/* ---------- DASHBOARD TAB ---------- */}
          {activeTab === "dashboard" && (
            <div>
              <div className="grid grid-cols-4 gap-5 mb-8">
                {[
                  { label: "Total Decisions Logged", value: totalEvents },
                  { label: "Total Transactions", value: totalTransactions },
                  { label: "Auto-Approved Orders", value: autoApprovedCount },
                  { label: "Active Promotions", value: promotionCount },
                ].map((stat) => (
                  <div key={stat.label} className="bg-white/5 border border-white/10 rounded-2xl p-5">
                    <p className="text-white/50 text-xs uppercase tracking-wider mb-2">{stat.label}</p>
                    <p className="text-3xl font-bold">{loading ? "—" : stat.value}</p>
                  </div>
                ))}
              </div>

              <p className="text-white/50 text-sm mb-4">Most recent decisions</p>
              <div className="space-y-3">
                {decisions.slice(0, 5).map((d) => (
                  <div key={d.id} className="bg-white/5 border border-white/10 rounded-xl p-4 flex justify-between items-center">
                    <div>
                      <span
                        className={`text-[10px] font-bold uppercase tracking-wide px-2.5 py-1 rounded-full mr-3 ${
                          DECISION_COLORS[d.decision_type] || "bg-white/10 text-white/70"
                        }`}
                      >
                        {d.decision_type.replace(/_/g, " ")}
                      </span>
                      <span className="text-white/70 text-sm">{d.reasoning?.slice(0, 80)}...</span>
                    </div>
                    <span className="text-white/30 text-xs whitespace-nowrap ml-4">
                      {new Date(d.timestamp).toLocaleString()}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* ---------- PROMOTIONS TAB ---------- */}
          {activeTab === "promotions" && (
            <div>
              {Object.keys(promotions).length === 0 ? (
                <p className="text-white/40 text-sm">
                  No active promotions right now — the merchant-agent updates these automatically
                  based on recent purchase demand.
                </p>
              ) : (
                <div className="grid grid-cols-3 gap-5">
                  {Object.entries(promotions).map(([category, details]) => (
                    <div key={category} className="bg-white/5 border border-white/10 rounded-2xl p-6">
                      <p className="text-pink-500 text-xs font-bold uppercase tracking-wider mb-2">{category}</p>
                      <p className="text-3xl font-bold mb-3">{details.discount_percentage}% off</p>
                      <p className="text-white/50 text-sm">{details.reason}</p>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* ---------- AUDIT TAB ---------- */}
          {activeTab === "audit" && (
            <div className="space-y-3">
              {loading ? (
                <p className="text-white/40 text-sm">Loading...</p>
              ) : decisions.length === 0 ? (
                <p className="text-white/40 text-sm">No decisions logged yet.</p>
              ) : (
                decisions.map((d) => (
                  <div key={d.id} className="bg-white/5 border border-white/10 rounded-xl p-4 hover:border-white/20 transition-colors">
                    <div className="flex justify-between items-start mb-2">
                      <span
                        className={`text-[10px] font-bold uppercase tracking-wide px-2.5 py-1 rounded-full ${
                          DECISION_COLORS[d.decision_type] || "bg-white/10 text-white/70"
                        }`}
                      >
                        {d.decision_type.replace(/_/g, " ")}
                      </span>
                      <span className="text-xs text-white/30">{new Date(d.timestamp).toLocaleString()}</span>
                    </div>
                    <p className="text-sm text-white/80 mb-2">{d.reasoning}</p>
                    <p className="text-xs text-white/20">Session: {d.session_id}</p>
                  </div>
                ))
              )}
            </div>
          )}
        </div>

        {/* ============ FOOTER ============ */}
        <div className="px-8 py-4 flex justify-between items-center text-[11px] text-white/40 border-t border-white/10">
          <p>
            <span className="text-pink-500">"Great style starts with trust."</span> VANE shops. You look good.
          </p>
          <div className="flex items-center gap-3 text-pink-500">
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