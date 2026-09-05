import { useNavigate } from "react-router-dom";

export default function Landing() {
  const navigate = useNavigate();

  return (
    <div className="min-h-screen relative flex items-center justify-center overflow-hidden text-white">
      <video autoPlay loop muted playsInline className="absolute inset-0 w-full h-full object-cover">
        <source src="/vid2.mp4" type="video/mp4" />
      </video>

      <div
        className="absolute inset-0 backdrop-blur-sm"
        style={{
          background:
            "radial-gradient(ellipse at center, rgba(0,0,0,0.4) 0%, rgba(0,0,0,0.68) 55%, rgba(0,0,0,0.95) 100%)",
        }}
      />

      {/* ============ TOP NAV ============ */}
      <div className="absolute top-0 left-0 right-0 z-20 flex justify-between items-center px-8 py-6">
        <h1 className="font-serif italic text-xl tracking-wide">vane.ai</h1>
        <div className="flex items-center gap-3 text-sm text-white/80">
          <button
            onClick={() => navigate("/merchant-login")}
            className="border border-white/25 text-white/70 hover:text-white hover:border-white/50 px-5 py-2 rounded-full text-sm font-medium transition-colors"
          >
            Merchant
          </button>
          <button
            onClick={() => navigate("/login")}
            className="border border-white/25 text-white/70 hover:text-white hover:border-white/50 px-5 py-2 rounded-full text-sm font-medium transition-colors"
          >
            Log in
          </button>
          <button
            onClick={() => navigate("/signup")}
            className="bg-white text-black px-5 py-2 rounded-full text-sm font-semibold hover:bg-white/90 transition-all"
          >
            Sign Up
          </button>
        </div>
      </div>

      {/* ============ HERO ============ */}
      <div className="relative z-10 flex flex-col items-center justify-center px-6 text-center max-w-3xl mx-4">
        <p className="text-white/60 text-xs font-semibold tracking-[0.3em] uppercase mb-4 drop-shadow-[0_2px_6px_rgba(0,0,0,0.9)]">
          Vane.ai
        </p>

        <h2 className="font-serif text-4xl md:text-5xl leading-tight mb-5 drop-shadow-[0_4px_18px_rgba(0,0,0,0.9)]">
          An Agent That Shops — On Your Terms
        </h2>

        <p className="text-white/85 mb-6 text-sm md:text-base leading-relaxed max-w-xl drop-shadow-[0_2px_10px_rgba(0,0,0,0.9)]">
          Tell it what you need, and Vane.ai takes it from there — searching the catalog,
          picking the item that best matches your request, and completing the purchase
          automatically. Anything above your set limit pauses for your approval before it
          goes through, and every decision is logged so you always know why it did what it did.
        </p>

        <div className="w-10 h-px bg-white/30 mb-6" />

        <button
          onClick={() => navigate("/signup")}
          className="bg-white text-black px-8 py-3 rounded-xl font-semibold hover:bg-white/90 transition-all mb-12 shadow-xl shadow-black/50"
        >
          Start Shopping
        </button>

        {/* ============ FEATURE ROW — one line, no wrap ============ */}
        <div className="flex flex-nowrap items-start justify-center gap-8 md:gap-12 w-full">
          <div className="flex items-center gap-3 text-left flex-shrink-0">
            <div className="w-11 h-11 rounded-full bg-black/40 backdrop-blur-sm border border-white/20 flex items-center justify-center flex-shrink-0 shadow-lg">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-white/80">
                <circle cx="11" cy="11" r="7" />
                <line x1="21" y1="21" x2="16.65" y2="16.65" />
              </svg>
            </div>
            <p className="text-white/90 text-xs leading-snug max-w-[130px] drop-shadow-[0_2px_6px_rgba(0,0,0,0.9)]">
              Search across vast catalogs
            </p>
          </div>

          <div className="flex items-center gap-3 text-left flex-shrink-0">
            <div className="w-11 h-11 rounded-full bg-black/40 backdrop-blur-sm border border-white/20 flex items-center justify-center flex-shrink-0 shadow-lg">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-white/80">
                <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" />
              </svg>
            </div>
            <p className="text-white/90 text-xs leading-snug max-w-[150px] drop-shadow-[0_2px_6px_rgba(0,0,0,0.9)]">
              Agent finds the best match and buys it for you
            </p>
          </div>

          <div className="flex items-center gap-3 text-left flex-shrink-0">
            <div className="w-11 h-11 rounded-full bg-black/40 backdrop-blur-sm border border-white/20 flex items-center justify-center flex-shrink-0 shadow-lg">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-white/80">
                <rect x="5" y="11" width="14" height="10" rx="2" />
                <path d="M8 11V7a4 4 0 0 1 8 0v4" />
              </svg>
            </div>
            <p className="text-white/90 text-xs leading-snug max-w-[140px] drop-shadow-[0_2px_6px_rgba(0,0,0,0.9)]">
              Big purchases pause for your approval
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}