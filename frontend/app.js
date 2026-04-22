/**
 * Con4mity — appels API (préfixe /api).
 *
 * Détection automatique :
 * - code-server : URL du type …/proxy/8001/…  → API = même origine + /proxy/8001/api
 * - accès direct : http://hôte:8001/…        → API = http://hôte:8001/api
 *
 * Surcharge manuelle (avant chargement de ce script) :
 *   window.CON4MITY_API_BASE = "http://con4mity.duckdns.org:33005/api";
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
    return "http://con4mity.duckdns.org:33005/api";
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
  if (!r.ok) throw new Error((await r.text()) || r.statusText);
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
