/**
 * Con4mity — appels API (préfixe /api).
 *
 * Détection automatique :
 * - code-server : URL du type …/proxy/8001/…  → API = même origine + /proxy/8001/api
 * - accès direct : http://hôte:8001/…        → API = http://hôte:8001/api
 *
 * Surcharge manuelle (avant chargement de ce script) :
 *   window.CON4MITY_API_BASE = "/api";
 */
/** Origine utilisable pour fetch() — 0.0.0.0 en hôte de page refuse souvent la connexion côté navigateur. */
function effectiveApiOrigin() {
  const { protocol, hostname, port } = window.location;
  const host =
    hostname === "0.0.0.0" || hostname === "[::]" ? "127.0.0.1" : hostname;
  const portPart = port ? `:${port}` : "";
  return `${protocol}//${host}${portPart}`;
}

function discoverApiBase() {
  if (typeof window === "undefined" || !window.location) {
    return "/api";
  }
  if (window.CON4MITY_API_BASE) {
    return String(window.CON4MITY_API_BASE).replace(/\/$/, "");
  }
  const origin = effectiveApiOrigin();
  const { pathname } = window.location;
  const proxy = pathname.match(/^(\/proxy\/\d+)/);
  if (proxy) {
    return `${origin}${proxy[1]}/api`.replace(/\/$/, "");
  }
  return `${origin}/api`.replace(/\/$/, "");
}

const API_BASE = discoverApiBase();

function apiQueryString(params) {
  if (!params || typeof params !== "object") return "";
  const u = new URLSearchParams();
  Object.keys(params).forEach((k) => {
    const v = params[k];
    if (v !== undefined && v !== null && String(v).trim() !== "") u.set(k, String(v));
  });
  const s = u.toString();
  return s ? `?${s}` : "";
}

function getToken() {
  return localStorage.getItem("con4mity_token") || "";
}

function authHeaders() {
  const t = getToken();
  const h = { "Content-Type": "application/json" };
  if (t) h["Authorization"] = `Bearer ${t}`;
  return h;
}

async function apiGet(path, params) {
  const p = path.startsWith("/") ? path : `/${path}`;
  const q = apiQueryString(params);
  const r = await fetch(`${API_BASE}${p}${q}`, { headers: authHeaders() });
  if (r.status === 401) {
    localStorage.removeItem("con4mity_token");
    window.location.href = "index.html";
    const msg =
      typeof window.t === "function"
        ? window.t("login.errorSession")
        : "Session expired or not authenticated";
    throw new Error(msg);
  }
  if (!r.ok) {
    const raw = (await r.text()) || r.statusText;
    const err = new Error();
    const ct = r.headers.get("content-type") || "";
    if (ct.includes("application/json")) {
      try {
        const j = JSON.parse(raw);
        err.message =
          (Array.isArray(j.detail) ? j.detail.map((d) => d.msg || d).join(" ") : j.detail) ||
          raw ||
          r.statusText;
      } catch (_) {
        err.message = raw || r.statusText;
      }
    } else {
      err.message = (raw && raw.slice(0, 500)) || r.statusText;
    }
    throw err;
  }
  return r.json();
}

async function apiPost(path, body) {
  const p = path.startsWith("/") ? path : `/${path}`;
  const r = await fetch(`${API_BASE}${p}`, {
    method: "POST",
    headers: authHeaders(),
    body: JSON.stringify(body),
  });
  if (r.status === 401) {
    localStorage.removeItem("con4mity_token");
    window.location.href = "index.html";
    const msg =
      typeof window.t === "function"
        ? window.t("login.errorSession")
        : "Session expired or not authenticated";
    throw new Error(msg);
  }
  if (!r.ok) throw new Error((await r.text()) || r.statusText);
  return r.json();
}

async function apiPatch(path, body) {
  const p = path.startsWith("/") ? path : `/${path}`;
  const r = await fetch(`${API_BASE}${p}`, {
    method: "PATCH",
    headers: authHeaders(),
    body: JSON.stringify(body),
  });
  if (r.status === 401) {
    localStorage.removeItem("con4mity_token");
    window.location.href = "index.html";
    const msg =
      typeof window.t === "function"
        ? window.t("login.errorSession")
        : "Session expired";
    throw new Error(msg);
  }
  if (!r.ok) throw new Error((await r.text()) || r.statusText);
  return r.json();
}

async function apiPut(path, body) {
  const p = path.startsWith("/") ? path : `/${path}`;
  const r = await fetch(`${API_BASE}${p}`, {
    method: "PUT",
    headers: authHeaders(),
    body: JSON.stringify(body),
  });
  if (r.status === 401) {
    localStorage.removeItem("con4mity_token");
    window.location.href = "index.html";
    throw new Error("Session expirée");
  }
  if (!r.ok) {
    const raw = (await r.text()) || r.statusText;
    let msg = raw;
    try {
      const j = JSON.parse(raw);
      if (j && j.detail) msg = Array.isArray(j.detail) ? j.detail.map((d) => d.msg || d).join(" ") : j.detail;
    } catch (_) {
      /* keep raw */
    }
    throw new Error(msg);
  }
  return r.json();
}

async function apiDelete(path) {
  const p = path.startsWith("/") ? path : `/${path}`;
  const r = await fetch(`${API_BASE}${p}`, { method: "DELETE", headers: authHeaders() });
  if (r.status === 401) {
    localStorage.removeItem("con4mity_token");
    window.location.href = "index.html";
    throw new Error("Session expirée");
  }
  if (!r.ok) {
    const raw = (await r.text()) || r.statusText;
    throw new Error(raw.slice(0, 500) || r.statusText);
  }
  if (r.status === 204) return null;
  const t = await r.text();
  return t ? JSON.parse(t) : null;
}

/**
 * WebSocket /api/stream — stats + volume 24h (mise à jour toutes ~3s).
 * Retourne une fonction close().
 */
function discoverStreamUrl() {
  const token = getToken();
  if (!token) return null;
  const origin = effectiveApiOrigin();
  const { pathname } = window.location;
  const proxy = pathname.match(/^(\/proxy\/\d+)/);
  const basePath = proxy ? proxy[1] : "";
  const u = new URL(origin);
  u.protocol = u.protocol === "https:" ? "wss:" : "ws:";
  u.pathname = `${basePath}/api/stream`.replace(/\/\//, "/");
  u.searchParams.set("token", token);
  return u.toString();
}

function connectCon4mityStream(onMessage) {
  const u = discoverStreamUrl();
  if (!u) return function noop() {};
  let ws;
  try {
    ws = new WebSocket(u);
  } catch {
    return function noop() {};
  }
  ws.onmessage = function (ev) {
    try {
      onMessage(JSON.parse(ev.data));
    } catch (_) {
      /* ignore */
    }
  };
  return function close() {
    try {
      if (ws && ws.readyState === WebSocket.OPEN) ws.close();
    } catch (_) {
      /* ignore */
    }
  };
}

/** URL d’export CSV (GET /api/logs/export.csv) — mêmes paramètres logiques que /logs. */
function buildLogsExportUrl(params) {
  const q = apiQueryString(params);
  return `${API_BASE}/logs/export.csv${q ? q : ""}`;
}
