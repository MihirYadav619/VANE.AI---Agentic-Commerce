import { useState } from "react";
import { useNavigate } from "react-router-dom";

export default function ModeSelection() {
  const navigate = useNavigate();
  const [hovered, setHovered] = useState(null);

  const chooseMode = (mode) => {
    localStorage.setItem("shopping_mode", mode);
    navigate("/shop");
  };

  return (
    <div className="min-h-screen w-full relative overflow-hidden bg-black">
      {/* Top brand bar */}
      <div className="absolute top-0 left-0 right-0 z-20 flex justify-between items-center px-8 py-6 text-white text-xs font-semibold tracking-widest">
        <span>VANE.AI</span>
        <span className="text-sm tracking-[0.3em]">CHOOSE YOUR MODE</span>
        <span className="opacity-0">VANE.AI</span>
      </div>

      <div className="flex flex-col md:flex-row min-h-screen w-full">
        {/* LEFT: Autonomous */}
        <div
          onClick={() => chooseMode("autonomous")}
          onMouseEnter={() => setHovered("autonomous")}
          onMouseLeave={() => setHovered(null)}
          className="group relative w-full md:w-1/2 min-h-[50vh] md:min-h-screen cursor-pointer overflow-hidden"
        >
          <div
            className="absolute inset-0 bg-cover bg-center transition-transform duration-700 ease-out group-hover:scale-110"
            style={{ backgroundImage: "url('/autonomous-side.png')" }}
          />
          <div className="absolute inset-0 bg-black/20 group-hover:bg-black/40 transition-all duration-500" />

          <div className="relative z-10 h-full flex items-center justify-center p-6">
            <div className="bg-white text-black px-10 py-8 text-center max-w-xs shadow-2xl">
              <p className="text-xs font-semibold tracking-widest text-gray-500 mb-2">
                AUTOPILOT
              </p>
              <h2 className="text-3xl font-black tracking-tight mb-2">
                AUTONOMOUS
              </h2>
              <p className="text-xs text-gray-600 mb-4">
                Let the AI shop, decide, and pay for you
              </p>
              <span className="text-xs font-bold tracking-widest border-b border-black pb-1 group-hover:pb-2 transition-all">
                SELECT →
              </span>
            </div>
          </div>
        </div>

        {/* RIGHT: Browse */}
        <div
          onClick={() => chooseMode("browse")}
          onMouseEnter={() => setHovered("browse")}
          onMouseLeave={() => setHovered(null)}
          className="group relative w-full md:w-1/2 min-h-[50vh] md:min-h-screen cursor-pointer overflow-hidden"
        >
          <div
            className="absolute inset-0 bg-cover bg-center transition-transform duration-700 ease-out group-hover:scale-110"
            style={{ backgroundImage: "url('/browse-side.png')" }}
          />
          <div className="absolute inset-0 bg-black/20 group-hover:bg-black/40 transition-all duration-500" />

          <div className="relative z-10 h-full flex items-center justify-center p-6">
            <div className="bg-black text-white px-10 py-8 text-center max-w-xs shadow-2xl">
              <p className="text-xs font-semibold tracking-widest text-gray-400 mb-2">
                MANUAL
              </p>
              <h2 className="text-3xl font-black tracking-tight mb-2">
                BROWSE
              </h2>
              <p className="text-xs text-gray-300 mb-4">
                See options yourself, agent just assists
              </p>
              <span className="text-xs font-bold tracking-widest border-b border-white pb-1 group-hover:pb-2 transition-all">
                SELECT →
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Center divider line (desktop only) */}
      <div className="hidden md:block absolute top-0 bottom-0 left-1/2 w-px bg-white/30 z-10" />
    </div>
  );
}