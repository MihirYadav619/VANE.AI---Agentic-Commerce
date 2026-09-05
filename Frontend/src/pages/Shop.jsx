import { useState, useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { logout } from "../api/auth";

const API_BASE = "http://localhost:8000";
const FALLBACK_IMAGE = "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='100' height='100'%3E%3Crect width='100' height='100' fill='%23e5e7eb'/%3E%3Ctext x='50' y='55' font-size='10' fill='%239CA3AF' text-anchor='middle'%3ENo Image%3C/text%3E%3C/svg%3E";
const REVEAL_DURATION_MS = 6500;

function ProductImage({ src, alt, className }) {
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

const STATUS_LABELS = {
  auto_approved: "Auto-Approved",
  approved_and_completed: "Approved",
  pending_approval: "Pending Approval",
  failed_stock_out: "Stock-Out",
  failed_payment: "Payment Failed",
};

const TRENDING_TILES = [
  { img: "/auto.jpg", label: "Overshirts" },
  { img: "/auto2.jpg", label: "Minimal Essentials" },
  { img: "/auto3.jpg", label: "Footwear" },
];

function ProductCard({ product, onAdd, badge, note }) {
  return (
    <div className="bg-white rounded-xl overflow-hidden shadow-sm border border-black/5 flex flex-col">
      <div className="aspect-square bg-gray-50 flex items-center justify-center p-3 relative">
        {badge && (
          <span className="absolute top-2 left-2 bg-black text-white text-[9px] font-bold uppercase tracking-wide px-2 py-0.5 rounded">
            {badge}
          </span>
        )}
        <ProductImage src={product.image_url} alt={product.name} className="w-full h-full object-contain" />
      </div>
      <div className="p-3 flex flex-col flex-1">
        <p className="text-gray-900 text-xs font-medium line-clamp-2 leading-snug mb-1 flex-1">
          {product.name}
        </p>
        <p className="text-gray-900 text-sm font-bold mb-1.5">₹{product.price}</p>
        {note && <p className="text-gray-400 text-[10px] mb-2 line-clamp-2">{note}</p>}
        <button
          onClick={() => onAdd(product)}
          className="w-full bg-black text-white text-xs font-semibold py-2 rounded-lg hover:bg-gray-800 transition-colors mt-auto"
        >
          Add to Cart
        </button>
      </div>
    </div>
  );
}

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

export default function Shop() {
  const navigate = useNavigate();
  const username = localStorage.getItem("username");
  const mode = localStorage.getItem("shopping_mode") || "autonomous";

  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [paymentStatus, setPaymentStatus] = useState(null);

  const [addonsOptedIn, setAddonsOptedIn] = useState(false);
  const [addonsBudget, setAddonsBudget] = useState(500);
  const [autoResult, setAutoResult] = useState(null);

  const [browseResult, setBrowseResult] = useState(null);

  const [cart, setCart] = useState([]);
  const [showCart, setShowCart] = useState(false);
  const [checkoutResult, setCheckoutResult] = useState(null);
  const [cartNudge, setCartNudge] = useState(null);

  const [revealData, setRevealData] = useState(null);
  const [progressWidth, setProgressWidth] = useState(0);
  const handledOrderIdRef = useRef(null);

  const [recentOrders, setRecentOrders] = useState([]);

  const handleLogout = () => {
    logout();
    navigate("/login");
  };

  const enrichOrdersWithProductInfo = async (orders) => {
    const enriched = await Promise.all(
      orders.map(async (o) => {
        if (o.image_url) return o;

        let itemIds = o.item_ids;
        if (typeof itemIds === "string") {
          try {
            itemIds = JSON.parse(itemIds);
          } catch {
            itemIds = null;
          }
        }

        const firstItemId = Array.isArray(itemIds) ? itemIds[0] : null;
        if (!firstItemId) return o;

        try {
          const res = await fetch(`${API_BASE}/catalog/product/${firstItemId}`);
          if (!res.ok) return o;
          const product = await res.json();
          return { ...o, image_url: product.image_url, name: product.name };
        } catch {
          return o;
        }
      })
    );
    return enriched;
  };

  const fetchRecentOrders = () => {
    fetch(`${API_BASE}/audit/recent-orders?limit=8`)
      .then((res) => {
        if (!res.ok) throw new Error("Not available");
        return res.json();
      })
      .then(async (data) => {
        const list = Array.isArray(data) ? data : [];
        const enriched = await enrichOrdersWithProductInfo(list);
        setRecentOrders(enriched);
      })
      .catch(() => setRecentOrders([]));
  };

  useEffect(() => {
    fetchRecentOrders();
  }, []);

  const openRazorpayCheckout = (orderId, keyId, amount) => {
    const script = document.createElement("script");
    script.src = "https://checkout.razorpay.com/v1/checkout.js";
    script.onload = () => {
      const options = {
        key: keyId,
        amount: amount * 100,
        currency: "INR",
        name: "Vane.ai",
        order_id: orderId,
        handler: function (response) {
          setPaymentStatus({ success: true, paymentId: response.razorpay_payment_id });
          fetchRecentOrders();
        },
        modal: {
          ondismiss: function () {
            setPaymentStatus({ success: false, message: "Payment cancelled." });
          },
        },
      };
      new window.Razorpay(options).open();
    };
    document.body.appendChild(script);
  };

  // ---------- AUTONOMOUS MODE ----------

  const handleAutoSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setAutoResult(null);
    setPaymentStatus(null);
    handledOrderIdRef.current = null;

    try {
      const res = await fetch(`${API_BASE}/order/build`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          query,
          mode: "autonomous",
          addons_opted_in: addonsOptedIn,
          addons_budget: addonsOptedIn ? Number(addonsBudget) : 0,
        }),
      });
      const data = await res.json();
      if (!res.ok) {
        setAutoResult({ status: "error", reasoning: data.detail || `Server error (${res.status})` });
      } else {
        setAutoResult(data);
      }
    } catch (err) {
      setAutoResult({ status: "error", reasoning: "Failed to reach the agent. Is the backend running?" });
    } finally {
      setLoading(false);
    }
  };

  const handleAutoApprove = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/order/approve`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          order_items: autoResult.order_items,
          order_total: autoResult.order_total,
          session_id: autoResult.session_id,
        }),
      });
      const data = await res.json();
      if (!res.ok) {
        alert(data.detail || `Approval failed (server error ${res.status}). Check backend logs.`);
      } else {
        setAutoResult({ ...autoResult, ...data });
      }
    } catch (err) {
      alert("Approval failed. Check backend logs.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    const ready = autoResult?.status === "auto_approved" || autoResult?.status === "approved_and_completed";
    if (!ready || !autoResult.razorpay_order_id) return;
    if (handledOrderIdRef.current === autoResult.razorpay_order_id) return;

    handledOrderIdRef.current = autoResult.razorpay_order_id;
    setRevealData({
      items: autoResult.order_items,
      total: autoResult.order_total,
      orderId: autoResult.razorpay_order_id,
      keyId: autoResult.razorpay_key_id,
    });
    setProgressWidth(0);
  }, [autoResult]);

  useEffect(() => {
    if (!revealData) return;
    const fillTimer = setTimeout(() => setProgressWidth(100), 50);
    const handoffTimer = setTimeout(() => {
      openRazorpayCheckout(revealData.orderId, revealData.keyId, revealData.total);
      setRevealData(null);
    }, REVEAL_DURATION_MS);
    return () => {
      clearTimeout(fillTimer);
      clearTimeout(handoffTimer);
    };
  }, [revealData]);

  // ---------- BROWSE MODE + CART ----------

  const handleBrowseSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setBrowseResult(null);
    setPaymentStatus(null);

    try {
      const res = await fetch(`${API_BASE}/order/build`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query, mode: "browse" }),
      });
      const data = await res.json();
      if (!res.ok) {
        setBrowseResult({ status: "error", reasoning: data.detail || `Server error (${res.status})` });
      } else {
        setBrowseResult(data);
      }
    } catch (err) {
      setBrowseResult({ status: "error", reasoning: "Failed to reach the agent." });
    } finally {
      setLoading(false);
    }
  };

  const addToCart = (product) => {
    setCart((prev) => {
      if (prev.find((p) => p.id === product.id)) return prev;
      return [...prev, product];
    });
  };

  const removeFromCart = (productId) => {
    setCart((prev) => prev.filter((p) => p.id !== productId));
  };

  const cartTotal = cart.reduce((sum, p) => sum + p.price, 0);

  useEffect(() => {
    if (cart.length === 0) {
      setCartNudge(null);
      return;
    }
    fetch(`${API_BASE}/cart/nudge`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ cart_total: cartTotal }),
    })
      .then((res) => res.json())
      .then((data) => setCartNudge(data))
      .catch(() => setCartNudge(null));
  }, [cart]);

  const handleCheckoutCart = async () => {
    setLoading(true);
    try {
      const sessionId = browseResult?.session_id || `cart_${Date.now()}`;
      const res = await fetch(`${API_BASE}/order/checkout-cart`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          product_ids: cart.map((p) => p.id),
          session_id: sessionId,
        }),
      });
      const data = await res.json();
      if (!res.ok) {
        alert(data.detail || `Checkout failed (server error ${res.status}). Check backend logs.`);
        return;
      }
      setCheckoutResult(data);
      if (data.status === "auto_approved") {
        openRazorpayCheckout(data.razorpay_order_id, data.razorpay_key_id, data.order_total);
        setCart([]);
      }
    } catch (err) {
      alert("Checkout failed. Check backend logs.");
    } finally {
      setLoading(false);
    }
  };

  const handleCartApprove = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/order/approve`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          order_items: checkoutResult.order_items,
          order_total: checkoutResult.order_total,
          session_id: checkoutResult.session_id,
        }),
      });
      const data = await res.json();
      if (!res.ok) {
        alert(data.detail || `Approval failed (server error ${res.status}).`);
        return;
      }
      setCheckoutResult({ ...checkoutResult, ...data });
      openRazorpayCheckout(data.razorpay_order_id, data.razorpay_key_id, checkoutResult.order_total);
      setCart([]);
    } catch (err) {
      alert("Approval failed.");
    } finally {
      setLoading(false);
    }
  };

  const AutoResultPanel = () => (
    <div className="bg-[#0d0d0d]/95 backdrop-blur-md border border-white/10 rounded-2xl p-6 shadow-2xl max-h-[40vh] overflow-y-auto">
      {autoResult.status === "no_match" && (
        <div>
          <p className="text-yellow-400 font-semibold mb-2">No genuine match found</p>
          <p className="text-white/70 text-sm">{autoResult.reasoning}</p>
        </div>
      )}
      {autoResult.status === "pending_approval" && (
        <div>
          <p className="text-orange-400 font-semibold mb-3">
            ⚠ Approval Required (₹{autoResult.order_total} exceeds ₹{autoResult.approval_threshold})
          </p>
          {autoResult.order_items.map((item) => (
            <div key={item.id} className="flex items-center gap-3 mb-3">
              <ProductImage src={item.image_url} alt={item.name} className="w-16 h-16 rounded-lg object-cover flex-shrink-0" />
              <div className="flex justify-between items-center w-full">
                <span className="text-sm">{item.name}</span>
                <span className="text-white/60 text-sm">₹{item.price}</span>
              </div>
            </div>
          ))}
          <button
            onClick={handleAutoApprove}
            disabled={loading}
            className="w-full bg-orange-500 text-white rounded-xl py-3 font-semibold hover:bg-orange-600 transition-all mt-4 disabled:opacity-50"
          >
            {loading ? "Processing..." : "Approve & Pay"}
          </button>
        </div>
      )}
      {autoResult.status === "error" && <p className="text-red-400 text-sm">{autoResult.reasoning}</p>}
    </div>
  );

  return (
    <div className="bg-black text-white">
      {mode === "autonomous" ? (
        <div className="h-screen overflow-hidden flex flex-col">
          <div className="flex justify-between items-center px-8 py-4 flex-shrink-0">
            <h1 className="text-lg font-semibold tracking-[0.3em] text-red-600">VANE.AI</h1>
            <div className="flex items-center gap-5 text-[11px] font-medium tracking-wider text-white/70">
              <button onClick={() => navigate("/audit")} className="hover:text-white transition-colors">
                AUDIT
              </button>
              <span className="text-white/20">|</span>
              <button onClick={handleLogout} className="hover:text-white transition-colors">
                LOGOUT
              </button>
              <div className="w-8 h-8 rounded-full border border-red-600 flex items-center justify-center text-xs font-bold uppercase ml-1">
                {username?.[0]}
              </div>
            </div>
          </div>

          <div className="flex-1 min-h-0 grid md:grid-cols-[1fr_400px]">
            <div
              className="relative flex flex-col justify-center bg-gray-900 bg-cover h-full min-h-0 overflow-y-auto"
              style={{ backgroundImage: "url(/autonomous-hero.png)", backgroundPosition: "25% center" }}
            >
              <div className="absolute inset-0 bg-gradient-to-r from-black/80 via-black/40 to-transparent" />
              <div className="relative z-10 px-10 md:px-16 py-8 w-full max-w-3xl">
                <p className="text-red-500 text-xs font-bold tracking-[0.35em] uppercase mb-4 drop-shadow-[0_2px_6px_rgba(0,0,0,0.8)]">
                  Your Personal Shopper
                </p>
                <h2 className="font-serif text-5xl md:text-7xl leading-[1.05] mb-5 drop-shadow-[0_4px_18px_rgba(0,0,0,0.85)]">
                  Tell <span className="text-red-600 italic">Vane</span>
                  <br />
                  what you're looking for.
                </h2>
                <p className="text-white/70 text-base mb-7 max-w-xl drop-shadow-[0_2px_8px_rgba(0,0,0,0.8)]">
                  The agent will search, decide and purchase the best options for you.
                </p>

                <form onSubmit={handleAutoSubmit} className="flex flex-col sm:flex-row gap-4 mb-5 max-w-2xl">
                  <div className="flex-1 flex items-center gap-3 bg-black/55 backdrop-blur-sm border border-white/20 rounded-md px-5 py-4 shadow-lg">
                    <span className="text-white/40 text-base">🔍</span>
                    <input
                      type="text"
                      value={query}
                      onChange={(e) => setQuery(e.target.value)}
                      placeholder="e.g. black leather jacket under ₹5000"
                      className="bg-transparent outline-none text-base text-white placeholder-white/50 w-full"
                      required
                    />
                  </div>
                  <button
                    type="submit"
                    disabled={loading}
                    className="bg-red-600 hover:bg-red-700 transition-colors text-white text-xs font-bold tracking-[0.15em] uppercase px-9 py-4 rounded-md disabled:opacity-50 whitespace-nowrap flex items-center justify-center gap-2 shadow-lg shadow-red-950/50"
                  >
                    {loading ? "Thinking..." : (<>Let Vane Shop <span>↗</span></>)}
                  </button>
                </form>

                <div className="flex items-start gap-3 mb-2">
                  <button
                    type="button"
                    onClick={() => setAddonsOptedIn(!addonsOptedIn)}
                    aria-pressed={addonsOptedIn}
                    className={`w-5 h-5 rounded-full border flex items-center justify-center flex-shrink-0 mt-0.5 transition-colors ${
                      addonsOptedIn ? "bg-red-600 border-red-600" : "border-white/50"
                    }`}
                  >
                    {addonsOptedIn && <span className="text-white text-[9px] leading-none">✓</span>}
                  </button>
                  <label className="text-base cursor-pointer" onClick={() => setAddonsOptedIn(!addonsOptedIn)}>
                    <span className="text-white font-medium block drop-shadow-[0_2px_6px_rgba(0,0,0,0.8)]">
                      Complete the look
                    </span>
                    <span className="block text-white/60 text-sm mt-0.5 drop-shadow-[0_2px_6px_rgba(0,0,0,0.8)]">
                      Let Vane build the full outfit around your request.
                    </span>
                  </label>
                </div>

                {addonsOptedIn && (
                  <div className="mb-6 mt-2">
                    <input
                      type="number"
                      value={addonsBudget}
                      onChange={(e) => setAddonsBudget(e.target.value)}
                      placeholder="Add-ons budget ₹"
                      className="bg-black/55 border border-white/20 rounded-md px-3 py-2 text-sm text-white w-44 focus:outline-none focus:ring-1 focus:ring-red-600"
                    />
                  </div>
                )}

                <p className="text-red-500 text-xs font-bold tracking-[0.35em] uppercase mb-4 mt-6 drop-shadow-[0_2px_6px_rgba(0,0,0,0.8)]">
                  Trending Now
                </p>
                <div className="grid grid-cols-3 gap-5 max-w-2xl">
                  {TRENDING_TILES.map((t) => (
                    <div
                      key={t.label}
                      className="relative aspect-square overflow-hidden rounded-lg shadow-xl shadow-black/50 group cursor-pointer ring-1 ring-white/10"
                    >
                      <img
                        src={t.img}
                        alt={t.label}
                        className="w-full h-full object-cover group-hover:scale-110 transition-transform duration-500"
                      />
                      <div className="absolute inset-0 bg-gradient-to-t from-black/85 via-black/15 to-transparent" />
                      <div className="absolute bottom-4 left-4">
                        <p className="text-sm font-bold uppercase tracking-wide leading-tight">{t.label}</p>
                        <p className="text-red-500 text-xs font-semibold mt-1">Explore →</p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            <div className="bg-gradient-to-b from-[#200808] to-black flex flex-col p-8 h-full min-h-0 overflow-hidden">
              <div className="flex items-center gap-3 pb-4 mb-4 border-b border-white/10 flex-shrink-0">
                <div className="w-11 h-11 rounded-full border-2 border-red-600 flex items-center justify-center font-bold uppercase flex-shrink-0">
                  {username?.[0]}
                </div>
                <div>
                  <p className="font-semibold text-sm">{username}</p>
                  <p className="text-xs text-white/50">Your personal shopper</p>
                </div>
              </div>

              <p className="text-red-500 text-[11px] font-bold tracking-[0.25em] uppercase mb-4 flex-shrink-0">
                Recent Orders
              </p>
              <div className="space-y-4 mb-4 flex-1 min-h-0 overflow-y-auto pr-1">
                {recentOrders.length === 0 ? (
                  <p className="text-white/40 text-sm">No orders yet — place your first order to see it here.</p>
                ) : (
                  recentOrders.map((o) => (
                    <div key={o.id} className="flex items-center gap-3">
                      <ProductImage
                        src={o.image_url}
                        alt={o.name || "order"}
                        className="w-12 h-12 rounded object-cover flex-shrink-0 bg-white/10"
                      />
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-semibold truncate">
                          {o.name || STATUS_LABELS[o.status] || o.status?.replace(/_/g, " ")}
                        </p>
                        <p className="text-[11px] text-white/40 mt-0.5">
                          {new Date(o.timestamp).toLocaleDateString("en-GB", {
                            day: "numeric",
                            month: "short",
                            year: "numeric",
                          })}
                        </p>
                      </div>
                      <p className="text-sm font-bold whitespace-nowrap">₹{o.order_total}</p>
                    </div>
                  ))
                )}
              </div>
              <button
                onClick={() => navigate("/audit")}
                className="w-full flex-shrink-0 flex items-center justify-center gap-2 border border-red-600 text-red-500 hover:bg-red-600 hover:text-white transition-colors text-[11px] font-bold tracking-wider uppercase py-2.5 rounded-md"
              >
                View All Orders →
              </button>
            </div>
          </div>

          <div className="px-8 py-3 flex flex-col sm:flex-row justify-between items-center gap-2 text-[11px] text-white/40 text-center sm:text-left flex-shrink-0">
            <p>
              <span className="text-red-500">"Great style starts with trust."</span>
              <br className="sm:hidden" /> VANE shops. You look good.
            </p>
            <div className="flex items-center gap-6 uppercase tracking-wider">
              <a href="#" className="hover:text-white transition-colors">About</a>
              <a href="#" className="hover:text-white transition-colors">Privacy</a>
              <a href="#" className="hover:text-white transition-colors">Terms</a>
              <a href="#" className="hover:text-white transition-colors">Help</a>
              <div className="flex items-center gap-3 text-red-600 normal-case">
                <a
                  href="https://www.linkedin.com/in/mihir-yadav-4509aa315/"
                  target="_blank"
                  rel="noopener noreferrer"
                  aria-label="LinkedIn"
                  className="hover:text-red-400 transition-colors"
                >
                  <LinkedInIcon />
                </a>
                <a
                  href="https://github.com/MihirYadav619/Agentic-Commerce"
                  target="_blank"
                  rel="noopener noreferrer"
                  aria-label="GitHub"
                  className="hover:text-red-400 transition-colors"
                >
                  <GitHubIcon />
                </a>
              </div>
            </div>
          </div>

          {((autoResult && !revealData) || paymentStatus) && (
            <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-30 w-[92%] max-w-xl">
              {autoResult && !revealData && <AutoResultPanel />}
              {paymentStatus && (
                <div
                  className={`mt-3 rounded-xl p-4 text-sm shadow-2xl backdrop-blur-md ${
                    paymentStatus.success ? "bg-green-500/20 text-green-300" : "bg-red-500/20 text-red-300"
                  }`}
                >
                  {paymentStatus.success
                    ? `✓ Payment successful! Payment ID: ${paymentStatus.paymentId}`
                    : paymentStatus.message}
                </div>
              )}
            </div>
          )}
        </div>
      ) : (
        <div className="h-screen overflow-hidden flex flex-col">
          <div className="flex justify-between items-center px-8 py-4 flex-shrink-0">
            <h1 className="text-lg font-semibold tracking-[0.3em] text-green-500">VANE.AI</h1>
            <div className="flex items-center gap-5 text-[11px] font-medium tracking-wider text-white/70">
              <button onClick={() => navigate("/audit")} className="hover:text-white transition-colors">
                AUDIT
              </button>
              <span className="text-white/20">|</span>
              <button onClick={() => setShowCart(!showCart)} className="relative hover:text-white transition-colors">
                CART
                {cart.length > 0 && (
                  <span className="absolute -top-2 -right-3 bg-green-500 text-black text-[9px] w-4 h-4 rounded-full flex items-center justify-center font-bold">
                    {cart.length}
                  </span>
                )}
              </button>
              <span className="text-white/20">|</span>
              <button onClick={handleLogout} className="hover:text-white transition-colors">
                LOGOUT
              </button>
              <div className="w-8 h-8 rounded-full border border-green-500 flex items-center justify-center text-xs font-bold uppercase ml-1">
                {username?.[0]}
              </div>
            </div>
          </div>

          <div className="flex-1 min-h-0 grid md:grid-cols-[1fr_420px]">
            <div
              className="relative flex flex-col justify-center bg-gray-900 bg-cover h-full min-h-0 overflow-y-auto"
              style={{ backgroundImage: "url(/browse-side2.png)", backgroundPosition: "25% center" }}
            >
              <div className="absolute inset-0 bg-gradient-to-r from-black/80 via-black/40 to-transparent" />
              <div className="relative z-10 px-10 md:px-16 py-8 w-full max-w-3xl">
                <p className="text-green-500 text-xs font-bold tracking-[0.35em] uppercase mb-4 drop-shadow-[0_2px_6px_rgba(0,0,0,0.8)]">
                  Your Personal Shopper
                </p>
                <h2 className="font-serif text-5xl md:text-7xl leading-[1.05] mb-5 drop-shadow-[0_4px_18px_rgba(0,0,0,0.85)]">
                  Tell <span className="text-green-500 italic">Vane</span>
                  <br />
                  what you're looking for.
                </h2>
                <p className="text-white/70 text-base mb-8 max-w-xl drop-shadow-[0_2px_8px_rgba(0,0,0,0.8)]">
                  The agent will search and bring you the best options — you decide what to buy.
                </p>

                <form onSubmit={handleBrowseSubmit} className="flex flex-col sm:flex-row gap-4 mb-5 max-w-2xl">
                  <div className="flex-1 flex items-center gap-3 bg-black/55 backdrop-blur-sm border border-white/20 rounded-md px-5 py-4 shadow-lg">
                    <span className="text-white/40 text-base">🔍</span>
                    <input
                      type="text"
                      value={query}
                      onChange={(e) => setQuery(e.target.value)}
                      placeholder="e.g. black leather jacket under ₹5000"
                      className="bg-transparent outline-none text-base text-white placeholder-white/50 w-full"
                      required
                    />
                  </div>
                  <button
                    type="submit"
                    disabled={loading}
                    className="bg-green-600 hover:bg-green-700 transition-colors text-white text-xs font-bold tracking-[0.15em] uppercase px-9 py-4 rounded-md disabled:opacity-50 whitespace-nowrap flex items-center justify-center gap-2 shadow-lg shadow-green-950/50"
                  >
                    {loading ? "Searching..." : (<>Let Vane Shop <span>↗</span></>)}
                  </button>
                </form>

                <p className="text-white/50 text-sm max-w-xl mb-7 drop-shadow-[0_2px_6px_rgba(0,0,0,0.8)]">
                  Search as many times as you like, add items to your cart, then checkout once.
                </p>

                <p className="text-green-500 text-xs font-bold tracking-[0.35em] uppercase mb-4 drop-shadow-[0_2px_6px_rgba(0,0,0,0.8)]">
                  Trending Now
                </p>
                <div className="grid grid-cols-3 gap-5 max-w-2xl">
                  {TRENDING_TILES.map((t) => (
                    <div
                      key={t.label}
                      className="relative aspect-square overflow-hidden rounded-lg shadow-xl shadow-black/50 group cursor-pointer ring-1 ring-white/10"
                    >
                      <img
                        src={t.img}
                        alt={t.label}
                        className="w-full h-full object-cover group-hover:scale-110 transition-transform duration-500"
                      />
                      <div className="absolute inset-0 bg-gradient-to-t from-black/85 via-black/15 to-transparent" />
                      <div className="absolute bottom-4 left-4">
                        <p className="text-sm font-bold uppercase tracking-wide leading-tight">{t.label}</p>
                        <p className="text-green-500 text-xs font-semibold mt-1">Explore →</p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            <div className="bg-gradient-to-b from-[#08200c] to-black flex flex-col p-7 h-full min-h-0 overflow-hidden">
              <div className="flex items-center justify-between pb-4 mb-4 border-b border-white/10 flex-shrink-0">
                <p className="text-green-500 text-[11px] font-bold tracking-[0.25em] uppercase">
                  Recommended For You
                </p>
                {cart.length > 0 && (
                  <button onClick={() => setShowCart(true)} className="text-white/50 hover:text-white text-[11px] transition-colors">
                    Cart ({cart.length})
                  </button>
                )}
              </div>

              <div className="flex-1 min-h-0 overflow-y-auto pr-1 space-y-6">
                {!browseResult && (
                  <p className="text-white/40 text-sm">
                    Search for something on the left to see recommendations here.
                  </p>
                )}

                {browseResult?.status === "no_match" && (
                  <div>
                    <p className="text-yellow-400 font-semibold mb-2 text-sm">No genuine match found</p>
                    <p className="text-white/60 text-xs">{browseResult.reasoning}</p>
                  </div>
                )}

                {browseResult?.status === "error" && (
                  <p className="text-red-400 text-sm">{browseResult.reasoning}</p>
                )}

                {browseResult?.status === "awaiting_human_selection" && (
                  <>
                    <div>
                      <h3 className="text-white text-[11px] font-bold uppercase tracking-widest mb-3">Best Match</h3>
                      <div className="grid grid-cols-2 gap-3">
                        <ProductCard
                          product={browseResult.main_product}
                          onAdd={addToCart}
                          note={browseResult.main_product_reasoning}
                        />
                        {browseResult.upsell_option?.should_suggest && browseResult.upsell_product && (
                          <ProductCard
                            product={browseResult.upsell_product}
                            onAdd={addToCart}
                            badge="Upgrade"
                            note={browseResult.upsell_option.reasoning}
                          />
                        )}
                      </div>
                    </div>

                    {browseResult.complete_the_look_products?.length > 0 && (
                      <div>
                        <h3 className="text-white text-[11px] font-bold uppercase tracking-widest mb-3">Complete The Look</h3>
                        <div className="grid grid-cols-2 gap-3">
                          {browseResult.complete_the_look_products.map((p) => (
                            <ProductCard key={p.id} product={p} onAdd={addToCart} />
                          ))}
                        </div>
                      </div>
                    )}

                    {browseResult.similar_items_products?.length > 0 && (
                      <div>
                        <h3 className="text-white text-[11px] font-bold uppercase tracking-widest mb-3">You Might Also Like</h3>
                        <div className="grid grid-cols-2 gap-3">
                          {browseResult.similar_items_products.map((p) => (
                            <ProductCard key={p.id} product={p} onAdd={addToCart} />
                          ))}
                        </div>
                      </div>
                    )}
                  </>
                )}
              </div>

              {cart.length > 0 && (
                <button
                  onClick={() => setShowCart(true)}
                  className="w-full flex-shrink-0 mt-4 flex items-center justify-center gap-2 border border-green-600 text-green-500 hover:bg-green-600 hover:text-white transition-colors text-[11px] font-bold tracking-wider uppercase py-2.5 rounded-md"
                >
                  View Cart ({cart.length}) →
                </button>
              )}
            </div>
          </div>

          <div className="px-8 py-3 flex flex-col sm:flex-row justify-between items-center gap-2 text-[11px] text-white/40 text-center sm:text-left flex-shrink-0">
            <p>
              <span className="text-green-500">"Great style starts with trust."</span>
              <br className="sm:hidden" /> VANE shops. You look good.
            </p>
            <div className="flex items-center gap-6 uppercase tracking-wider">
              <a href="#" className="hover:text-white transition-colors">About</a>
              <a href="#" className="hover:text-white transition-colors">Privacy</a>
              <a href="#" className="hover:text-white transition-colors">Terms</a>
              <a href="#" className="hover:text-white transition-colors">Help</a>
              <div className="flex items-center gap-3 text-green-500 normal-case">
                <a
                  href="https://www.linkedin.com/in/mihir-yadav-4509aa315/"
                  target="_blank"
                  rel="noopener noreferrer"
                  aria-label="LinkedIn"
                  className="hover:text-green-400 transition-colors"
                >
                  <LinkedInIcon />
                </a>
                <a
                  href="https://github.com/MihirYadav619/Agentic-Commerce"
                  target="_blank"
                  rel="noopener noreferrer"
                  aria-label="GitHub"
                  className="hover:text-green-400 transition-colors"
                >
                  <GitHubIcon />
                </a>
              </div>
            </div>
          </div>

          {paymentStatus && (
            <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-30 w-[92%] max-w-xl">
              <div
                className={`rounded-xl p-4 text-sm shadow-2xl backdrop-blur-md ${
                  paymentStatus.success ? "bg-green-500/20 text-green-300" : "bg-red-500/20 text-red-300"
                }`}
              >
                {paymentStatus.success
                  ? `✓ Payment successful! Payment ID: ${paymentStatus.paymentId}`
                  : paymentStatus.message}
              </div>
            </div>
          )}
        </div>
      )}

      {revealData && (
        <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/95 backdrop-blur-md p-6">
          <div className="animate-[revealIn_0.6s_ease-out] w-full max-w-3xl">
            <p className="text-green-400 text-xs font-semibold tracking-widest uppercase text-center mb-6">
              ✓ Agent found your match
            </p>

            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
              <div className="opacity-0 animate-[fadeInUp_0.5s_ease-out_forwards] bg-white rounded-xl overflow-hidden shadow-2xl">
                <div className="aspect-square bg-white flex items-center justify-center p-2">
                  <ProductImage src={revealData.items[0]?.image_url} alt={revealData.items[0]?.name} className="w-full h-full object-contain" />
                </div>
                <div className="p-3 bg-white">
                  <p className="text-gray-900 text-xs font-medium line-clamp-2 leading-snug mb-1">{revealData.items[0]?.name}</p>
                  <p className="text-gray-500 text-xs font-semibold">₹{revealData.items[0]?.price}</p>
                </div>
              </div>

              {revealData.items.slice(1).map((item, index) => (
                <div
                  key={item.id}
                  className="opacity-0 animate-[fadeInUp_0.5s_ease-out_forwards] bg-white rounded-xl overflow-hidden shadow-2xl"
                  style={{ animationDelay: `${0.3 + index * 0.25}s` }}
                >
                  <div className="aspect-square bg-white flex items-center justify-center p-2">
                    <ProductImage src={item.image_url} alt={item.name} className="w-full h-full object-contain" />
                  </div>
                  <div className="p-3 bg-white">
                    <p className="text-gray-900 text-xs font-medium line-clamp-2 leading-snug mb-1">{item.name}</p>
                    <p className="text-gray-500 text-xs font-semibold">₹{item.price}</p>
                  </div>
                </div>
              ))}
            </div>

            <div className="text-center">
              <p className="text-2xl font-black text-white mb-6">Total: ₹{revealData.total}</p>
              <p className="text-white/40 text-xs mb-3">Preparing secure checkout...</p>
              <div className="w-64 h-1 bg-white/10 rounded-full overflow-hidden mx-auto">
                <div
                  className="h-full bg-white rounded-full"
                  style={{ width: `${progressWidth}%`, transition: `width ${REVEAL_DURATION_MS}ms linear` }}
                />
              </div>
            </div>
          </div>
        </div>
      )}

      {showCart && (
        <div className="fixed inset-0 bg-black/70 z-50 flex justify-end" onClick={() => setShowCart(false)}>
          <div className="bg-gray-900 w-full max-w-md h-full p-6 overflow-y-auto border-l border-white/10" onClick={(e) => e.stopPropagation()}>
            <div className="flex justify-between items-center mb-6">
              <h3 className="text-xl font-bold">Your Cart</h3>
              <button onClick={() => setShowCart(false)} className="text-white/50 hover:text-white">✕</button>
            </div>

            {cart.length === 0 ? (
              <p className="text-white/50">Cart is empty. Search for something and add items.</p>
            ) : (
              <>
                {cart.map((item) => (
                  <div key={item.id} className="flex items-center gap-3 mb-3 bg-white/5 rounded-lg p-3">
                    <ProductImage src={item.image_url} alt={item.name} className="w-14 h-14 rounded-lg object-cover flex-shrink-0" />
                    <div className="flex-1 flex justify-between items-center">
                      <div>
                        <p className="text-sm font-medium">{item.name}</p>
                        <p className="text-xs text-white/50">₹{item.price}</p>
                      </div>
                      <button onClick={() => removeFromCart(item.id)} className="text-red-400 text-xs">Remove</button>
                    </div>
                  </div>
                ))}
                <div className="border-t border-white/10 mt-4 pt-4">
                  <p className="text-lg font-bold mb-4">Total: ₹{cartTotal}</p>
                  {cartNudge?.message && (
                    <div className={`mb-4 rounded-lg p-3 text-xs ${cartNudge.already_unlocked ? "bg-green-500/20 text-green-300" : "bg-blue-500/20 text-blue-300"}`}>
                      {cartNudge.already_unlocked ? "🎉 " : "💡 "}{cartNudge.message}
                    </div>
                  )}
                  <button onClick={handleCheckoutCart} disabled={loading} className="w-full bg-white text-black rounded-xl py-3 font-semibold hover:bg-white/90 transition-all disabled:opacity-50">
                    {loading ? "Processing..." : "Checkout"}
                  </button>
                </div>
                {checkoutResult?.status === "pending_approval" && (
                  <div className="mt-4 bg-orange-500/20 border border-orange-400/30 rounded-lg p-4">
                    <p className="text-orange-300 text-sm mb-3">
                      ⚠ Approval required (₹{checkoutResult.order_total} exceeds ₹{checkoutResult.approval_threshold})
                    </p>
                    <button onClick={handleCartApprove} disabled={loading} className="w-full bg-orange-500 text-white rounded-lg py-2 text-sm font-semibold hover:bg-orange-600 disabled:opacity-50">
                      {loading ? "Processing..." : "Approve & Pay"}
                    </button>
                  </div>
                )}
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}