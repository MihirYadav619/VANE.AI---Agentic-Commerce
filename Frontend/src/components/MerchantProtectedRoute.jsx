import { Navigate } from "react-router-dom";

export default function MerchantProtectedRoute({ children }) {
  const isMerchant = localStorage.getItem("merchant_authenticated") === "true";
  return isMerchant ? children : <Navigate to="/merchant-login" replace />;
}