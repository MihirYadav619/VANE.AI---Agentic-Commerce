const API_BASE = "http://localhost:8000";

export async function signup(username, password) {
  const res = await fetch(`${API_BASE}/auth/signup`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });
  if (!res.ok) throw new Error((await res.json()).detail);
  const data = await res.json();
  localStorage.setItem("token", data.token);
  localStorage.setItem("username", data.username);
  return data;
}

export async function login(username, password) {
  const res = await fetch(`${API_BASE}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });
  if (!res.ok) throw new Error((await res.json()).detail);
  const data = await res.json();
  localStorage.setItem("token", data.token);
  localStorage.setItem("username", data.username);
  return data;
}

export function logout() {
  localStorage.removeItem("token");
  localStorage.removeItem("username");
}

export function getToken() {
  return localStorage.getItem("token");
}

export function isLoggedIn() {
  return !!getToken();
}