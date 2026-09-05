import { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { login } from "../api/auth";

export default function Login() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    try {
      await login(username, password);
      navigate("/mode");
    } catch (err) {
      setError(err.message);
    }
  };

  return (
    <div className="min-h-screen relative flex items-center justify-center overflow-hidden">
      <video autoPlay loop muted playsInline className="absolute inset-0 w-full h-full object-cover">
        <source src="/vid2.mp4" type="video/mp4" />
      </video>

      <div
        className="absolute inset-0 backdrop-blur-sm"
        style={{
          background:
            "radial-gradient(ellipse at center, rgba(0,0,0,0.25) 0%, rgba(0,0,0,0.55) 55%, rgba(0,0,0,0.92) 100%)",
        }}
      />

      <div className="relative z-10 w-full max-w-md mx-4">
        <div className="bg-white/10 backdrop-blur-2xl border border-white/20 rounded-2xl shadow-2xl p-8 md:p-10">
          <div className="flex justify-center mb-6">
            <img
              src="/logo.png"
              alt="Vane.ai"
              className="h-24 w-24 object-contain mix-blend-screen"
            />
          </div>

          <h1 className="text-3xl font-bold text-white mb-2 text-center">Welcome Back!</h1>
          <p className="text-white/70 mb-8 text-center">Please enter your details to sign in</p>

          {error && (
            <p className="text-red-200 text-sm mb-4 bg-red-500/20 border border-red-400/30 rounded-lg px-3 py-2">
              {error}
            </p>
          )}

          <form onSubmit={handleSubmit} className="space-y-5">
            <div>
              <label className="block text-sm font-medium text-white/80 mb-1.5">Username</label>
              <input
                type="text"
                placeholder="Enter your username"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                className="w-full bg-white/10 border border-white/20 rounded-lg px-4 py-2.5 text-white placeholder-white/40 focus:outline-none focus:ring-2 focus:ring-white/50 focus:bg-white/20 transition-all"
                required
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-white/80 mb-1.5">Password</label>
              <input
                type="password"
                placeholder="Enter your password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full bg-white/10 border border-white/20 rounded-lg px-4 py-2.5 text-white placeholder-white/40 focus:outline-none focus:ring-2 focus:ring-white/50 focus:bg-white/20 transition-all"
                required
              />
            </div>

            <button type="submit" className="w-full bg-white text-gray-900 rounded-lg py-2.5 font-semibold hover:bg-white/90 transition-all shadow-lg">
              Sign in
            </button>
          </form>

          <p className="text-sm text-center text-white/70 mt-6">
            Don't have an account? <Link to="/signup" className="text-white font-semibold hover:underline">Sign up</Link>
          </p>
        </div>
      </div>
    </div>
  );
}