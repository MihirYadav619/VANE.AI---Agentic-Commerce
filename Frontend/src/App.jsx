import { BrowserRouter, Routes, Route } from "react-router-dom";
import Landing from "./pages/Landing";
import Login from "./pages/Login";
import Signup from "./pages/Signup";
import ModeSelection from "./pages/ModeSelection";
import Shop from "./pages/Shop";
import AuditDashboard from "./pages/AuditDashboard";
import MerchantLogin from "./pages/MerchantLogin";
import MerchantDashboard from "./pages/MerchantDashboard";
import ProtectedRoute from "./components/ProtectedRoute";
import MerchantProtectedRoute from "./components/MerchantProtectedRoute";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Landing />} />
        <Route path="/login" element={<Login />} />
        <Route path="/signup" element={<Signup />} />
        <Route path="/merchant-login" element={<MerchantLogin />} />
        <Route
          path="/merchant"
          element={
            <MerchantProtectedRoute>
              <MerchantDashboard />
            </MerchantProtectedRoute>
          }
        />
        <Route
          path="/mode"
          element={
            <ProtectedRoute>
              <ModeSelection />
            </ProtectedRoute>
          }
        />
        <Route
          path="/shop"
          element={
            <ProtectedRoute>
              <Shop />
            </ProtectedRoute>
          }
        />
        <Route
          path="/audit"
          element={
            <ProtectedRoute>
              <AuditDashboard />
            </ProtectedRoute>
          }
        />
      </Routes>
    </BrowserRouter>
  );
}