/**
 * MedRAG – API Client
 * Centralised fetch wrapper with JWT Bearer injection,
 * auto token-refresh, and error normalisation.
 */

// Use relative path so nginx proxy works in Docker; fall back to direct for local dev
const API_BASE = window.location.port === "5500"
  ? "http://127.0.0.1:8000/api/v1"
  : "/api/v1";

/* ── Token Storage ──────────────────────────────────────────────────────── */
const TokenStore = {
  get access()  { return localStorage.getItem("medrag_access"); },
  get refresh() { return localStorage.getItem("medrag_refresh"); },
  set(access, refresh) {
    localStorage.setItem("medrag_access",  access);
    localStorage.setItem("medrag_refresh", refresh);
  },
  clear() {
    localStorage.removeItem("medrag_access");
    localStorage.removeItem("medrag_refresh");
    localStorage.removeItem("medrag_doctor");
  },
};

/* ── Doctor Profile Cache ───────────────────────────────────────────────── */
const DoctorStore = {
  get() {
    try { return JSON.parse(localStorage.getItem("medrag_doctor") || "null"); }
    catch { return null; }
  },
  set(data) { localStorage.setItem("medrag_doctor", JSON.stringify(data)); },
  clear()   { localStorage.removeItem("medrag_doctor"); },
};

/* ── Core Fetch ─────────────────────────────────────────────────────────── */
let _refreshPromise = null;

async function apiFetch(endpoint, options = {}) {
  const url = endpoint.startsWith("http") ? endpoint : `${API_BASE}${endpoint}`;

  const headers = {
    "Content-Type": "application/json",
    ...(options.headers || {}),
  };

  // Inject bearer token (skip for auth endpoints)
  const isAuthEndpoint = endpoint.includes("/auth/login") || endpoint.includes("/auth/register");
  if (!isAuthEndpoint && TokenStore.access) {
    headers["Authorization"] = `Bearer ${TokenStore.access}`;
  }

  let response = await fetch(url, { ...options, headers });

  // ── Auto-refresh on 401 ──────────────────────────────────────────────────
  if (response.status === 401 && TokenStore.refresh && !isAuthEndpoint) {
    if (!_refreshPromise) {
      _refreshPromise = _doRefresh().finally(() => { _refreshPromise = null; });
    }
    const refreshed = await _refreshPromise;
    if (refreshed) {
      headers["Authorization"] = `Bearer ${TokenStore.access}`;
      response = await fetch(url, { ...options, headers });
    } else {
      TokenStore.clear();
      window.location.href = "index.html";
      throw new Error("Session expired. Please log in again.");
    }
  }

  return response;
}

async function _doRefresh() {
  try {
    const res = await fetch(`${API_BASE}/auth/token/refresh/`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh: TokenStore.refresh }),
    });
    if (!res.ok) return false;
    const data = await res.json();
    TokenStore.set(data.access, data.refresh || TokenStore.refresh);
    return true;
  } catch {
    return false;
  }
}

/* ── JSON helpers ───────────────────────────────────────────────────────── */
async function apiGet(endpoint) {
  const res = await apiFetch(endpoint, { method: "GET" });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw Object.assign(new Error(err.detail || err.error || "Request failed"), { status: res.status, data: err });
  }
  return res.json();
}

async function apiPost(endpoint, body) {
  const res = await apiFetch(endpoint, {
    method: "POST",
    body: JSON.stringify(body),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw Object.assign(new Error(data.detail || data.error || "Request failed"), { status: res.status, data });
  return data;
}

async function apiPatch(endpoint, body) {
  const res = await apiFetch(endpoint, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw Object.assign(new Error(data.detail || data.error || "Request failed"), { status: res.status, data });
  return data;
}

async function apiDelete(endpoint) {
  const res = await apiFetch(endpoint, { method: "DELETE" });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw Object.assign(new Error(err.detail || "Delete failed"), { status: res.status });
  }
  return true;
}

async function apiUpload(endpoint, formData) {
  const headers = {};
  if (TokenStore.access) headers["Authorization"] = `Bearer ${TokenStore.access}`;
  const res = await fetch(`${API_BASE}${endpoint}`, {
    method: "POST",
    headers,
    body: formData,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw Object.assign(new Error(data.detail || data.error || "Upload failed"), { status: res.status, data });
  return data;
}

/* ── Toast notifications ────────────────────────────────────────────────── */
function showToast(message, type = "info", duration = 4000) {
  const container = document.getElementById("toastContainer");
  if (!container) return;

  const toast = document.createElement("div");
  toast.className = `toast toast-${type}`;
  toast.innerHTML = `
    <svg width="14" height="14" viewBox="0 0 14 14" fill="none" style="flex-shrink:0">
      ${type === "success" ? '<path d="M2 7l3.5 3.5L12 4" stroke="#4ade80" stroke-width="1.5" stroke-linecap="round"/>' :
        type === "error"   ? '<path d="M3 3l8 8M11 3L3 11" stroke="#f87171" stroke-width="1.5" stroke-linecap="round"/>' :
        type === "warning" ? '<path d="M7 5v3M7 9.5v.5" stroke="#fbbf24" stroke-width="1.5" stroke-linecap="round"/>' :
                             '<circle cx="7" cy="7" r="5" stroke="#00d4b4" stroke-width="1.5"/>'}
    </svg>
    <span>${message}</span>`;

  container.appendChild(toast);
  setTimeout(() => toast.style.opacity = "0", duration - 300);
  setTimeout(() => toast.remove(), duration);
}

/* ── Utility ─────────────────────────────────────────────────────────────── */
function formatDate(isoString) {
  if (!isoString) return "—";
  const d = new Date(isoString);
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" })
    + " " + d.toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit" });
}

function escapeHtml(text) {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

/** Rudimentary markdown-to-HTML (bold, headers, bullets) */
function renderMarkdown(text) {
  return text
    .replace(/^### (.+)$/gm, "<h3>$1</h3>")
    .replace(/^## (.+)$/gm, "<h2>$1</h2>")
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/^\* (.+)$/gm, "<li>$1</li>")
    .replace(/(<li>[\s\S]+?<\/li>)/g, "<ul>$1</ul>")
    .replace(/\n\n/g, "<br/><br/>")
    .replace(/\n/g, "<br/>");
}
