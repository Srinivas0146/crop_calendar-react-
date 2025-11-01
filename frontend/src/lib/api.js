const BASE = import.meta.env.VITE_API_BASE || "http://127.0.0.1:8000";

function authHeaders() {
  const token = localStorage.getItem("token");
  return token ? { Authorization: `Bearer ${token}` } : {};
}

// Small helper: fetch with timeout + better errors
async function fetchJSON(url, opts = {}, timeoutMs = 20000) {
  const controller = new AbortController();
  const t = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const res = await fetch(url, { ...opts, signal: controller.signal });
    if (!res.ok) {
      const txt = await res.text().catch(() => "");
      // Make server errors readable in UI
      throw new Error(txt || `HTTP ${res.status}`);
    }
    return await res.json();
  } catch (err) {
    if (err.name === "AbortError") throw new Error("Request timed out");
    // Pass through readable message
    throw new Error(err.message || "Network error");
  } finally {
    clearTimeout(t);
  }
}

export const api = {
  async signup(username, password) {
    return fetchJSON(`${BASE}/auth/signup`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password })
    });
  },
  async login(username, password) {
    const form = new URLSearchParams();
    form.set("username", username); form.set("password", password);
    return fetchJSON(`${BASE}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: form.toString()
    });
  },
  async me() {
    return fetchJSON(`${BASE}/me`, { headers: { ...authHeaders() } });
  },
  async states() {
    return fetchJSON(`${BASE}/states`);
  },
  async geocode(query) {
    return fetchJSON(`${BASE}/geocode?query=${encodeURIComponent(query)}`);
  },
  async seasonNow(state) {
    return fetchJSON(`${BASE}/season_now?state=${encodeURIComponent(state)}`);
  },
  async liveCrops(state, season) {
    const qs = new URLSearchParams({ state, season: season ?? "" });
    return fetchJSON(`${BASE}/live_crops?${qs.toString()}`);
  },
  async logEvent(event_name, meta) {
    return fetchJSON(`${BASE}/analytics/event`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...authHeaders() },
      body: JSON.stringify({ event_name, meta })
    });
  }
};
