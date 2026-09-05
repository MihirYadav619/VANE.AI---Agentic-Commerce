import { useState } from "react";
import { useNavigate } from "react-router-dom";

// Single shared password since there's only one merchant who owns the
// catalog — not per-account auth like the customer-facing login.
const MERCHANT_PASSWORD = "vane-merchant-2026";

export default function MerchantLogin() {
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const navigate = useNavigate();

  const handleSubmit = (e) => {
    e.preventDefault();
    if (password === MERCHANT_PASSWORD) {
      localStorage.setItem("merchant_authenticated", "true");
      navigate("/merchant");
    } else {
      setError("Incorrect password.");
    }
  };

  return (
    <div className="min-h-screen bg-black text-white flex items-center justify-center px-6">
      <div
        className="absolute inset-0 bg-cover bg-center opacity-20 pointer-events-none"
        style={{ backgroundImage: "url(/audit-bg.png)" }}
      />
      <div className="relative w-full max-w-sm bg-white/5 border border-white/10 rounded-2xl p-8">
        <p className="text-pink-500 text-xs font-bold tracking-[0.35em] uppercase mb-3">
          Merchant Access
        </p>
        <h1 className="font-serif text-3xl mb-6">
          <span className="text-pink-500 italic">Vane</span> for Merchants
        </h1>

        {error && (
          <p className="text-red-300 text-sm mb-4 bg-red-500/10 border border-red-500/30 rounded-lg px-3 py-2">
            {error}
          </p>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-xs text-white/60 mb-1.5">Password</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Enter merchant password"
              className="w-full bg-white/10 border border-white/20 rounded-lg px-4 py-2.5 text-white placeholder-white/40 focus:outline-none focus:ring-2 focus:ring-pink-600"
              required
            />
          </div>
          <button
            type="submit"
            className="w-full bg-pink-600 hover:bg-pink-700 transition-colors text-white rounded-lg py-3 font-semibold"
          >
            Enter Dashboard
          </button>
        </form>
      </div>
    </div>
  );
}