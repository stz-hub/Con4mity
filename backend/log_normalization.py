"""
Normalisation des documents OpenSearch hétérogènes (syslog brut, ECS, champs plats).

Utilisé par l’agrégation overview et l’enrichissement des réponses /api/logs.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from typing import Any

# Hôte après horodatage style BSD : "Apr 21 19:58:01 myhost CRON[123]:"
_BSD_SYSLOG_HOST = re.compile(
    r"^[A-Za-z]{3}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2}\s+(\S+)",
)
# Hôte après ISO dans une ligne log : "...T19:58:01.855Z myhost ..."
_ISO_THEN_HOST = re.compile(
    r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z\s+(\S+)",
)
_PRI = re.compile(r"^<(\d{1,3})>")
_IP = re.compile(
    r"\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b",
)


def _as_text(v: Any, max_len: int = 8000) -> str:
    if v is None:
        return ""
    if isinstance(v, str):
        return v if len(v) <= max_len else v[:max_len] + "…"
    if isinstance(v, (dict, list)):
        try:
            s = json.dumps(v, ensure_ascii=False)
        except (TypeError, ValueError):
            s = str(v)
        return s if len(s) <= max_len else s[:max_len] + "…"
    return str(v)


def _strip_syslog_pri(line: str) -> str:
    s = line.strip()
    if s.startswith("<") and ">" in s[:5]:
        return s[s.index(">") + 1 :].lstrip()
    return s


def extract_syslog_host(line: str) -> str | None:
    """Déduit l’hôte depuis une ligne syslog BSD ou un champ `log` texte."""
    if not line or not isinstance(line, str):
        return None
    s = _strip_syslog_pri(line)
    m = _BSD_SYSLOG_HOST.match(s)
    if m:
        cand = m.group(1)
        if cand and not cand.isdigit():
            return cand
    m2 = _ISO_THEN_HOST.search(line)
    if m2:
        return m2.group(1)
    return None


def pick_timestamp_raw(doc: dict[str, Any]) -> str | None:
    v = doc.get("@timestamp") or doc.get("received_at") or doc.get("timestamp")
    return str(v) if v else None


def pick_host(doc: dict[str, Any]) -> str:
    h = doc.get("host")
    if isinstance(h, dict):
        name = h.get("name") or h.get("hostname")
        if name:
            return str(name)
    if isinstance(h, str) and h.strip():
        return h.strip()
    hn = doc.get("host.name")
    if hn and isinstance(hn, str) and hn.strip():
        return hn.strip()
    v = doc.get("hostname")
    if v and isinstance(v, str) and v.strip():
        return v.strip()
    ag = doc.get("agent")
    if isinstance(ag, dict) and ag.get("hostname"):
        return str(ag["hostname"])
    logv = doc.get("log")
    if isinstance(logv, str):
        eh = extract_syslog_host(logv)
        if eh:
            return eh
    msg = doc.get("message") or doc.get("raw_message") or doc.get("event.original")
    if isinstance(msg, str):
        eh = extract_syslog_host(msg)
        if eh:
            return eh
    return "—"


def _pri_to_label(pri: int) -> str:
    sev = max(0, min(7, pri % 8))
    return (
        "emergency",
        "alert",
        "critical",
        "error",
        "warning",
        "notice",
        "info",
        "debug",
    )[sev]


def pick_severity(doc: dict[str, Any]) -> str:
    v = doc.get("severity")
    if v is not None and str(v).strip() != "":
        return str(v).strip().lower()
    ll = doc.get("log.level")
    if ll is not None and str(ll).strip() != "":
        return str(ll).strip().lower()
    lv = doc.get("level")
    if lv is not None and str(lv).strip() != "":
        return str(lv).strip().lower()
    lg = doc.get("log")
    if isinstance(lg, dict) and lg.get("level"):
        return str(lg["level"]).lower()
    for blob in (doc.get("log"), doc.get("message"), doc.get("raw_message")):
        if not isinstance(blob, str):
            continue
        s = blob.strip()
        m = _PRI.match(s)
        if m:
            try:
                return _pri_to_label(int(m.group(1)))
            except ValueError:
                pass
        u = s.upper()
        if " EMERG " in u or " EMERGENCY" in u:
            return "emergency"
        if " ALERT " in u:
            return "alert"
        if " CRIT " in u or " CRITICAL" in u:
            return "critical"
        if " ERR " in u or " ERROR " in u:
            return "error"
        if " WARN " in u or "WARNING" in u:
            return "warning"
        if " NOTICE " in u:
            return "notice"
        if " DEBUG " in u:
            return "debug"
    ev = doc.get("event")
    if isinstance(ev, dict):
        if ev.get("severity") is not None:
            try:
                n = float(ev["severity"])
                if n >= 21:
                    return "critical"
                if n >= 14:
                    return "high"
                if n >= 8:
                    return "medium"
                if n > 0:
                    return "low"
            except (TypeError, ValueError):
                pass
        if ev.get("type"):
            return str(ev["type"]).lower()[:48]
    return "info"


def pick_message(doc: dict[str, Any], table_max: int = 480) -> str:
    for key in ("message", "raw_message", "event.original"):
        v = doc.get(key)
        if isinstance(v, str) and v.strip():
            t = v.strip()
            return t if len(t) <= table_max else t[: table_max - 1] + "…"
    logv = doc.get("log")
    if isinstance(logv, str) and logv.strip():
        t = logv.strip()
        return t if len(t) <= table_max else t[: table_max - 1] + "…"
    if isinstance(logv, dict):
        t = _as_text(logv, 2000)
        return t if len(t) <= table_max else t[: table_max - 1] + "…"
    # Dernier recours : aperçu JSON stable (sans tout le document)
    skip = {"_id", "_index", "_score"}
    slim = {k: v for k, v in doc.items() if k not in skip and not str(k).startswith("con4mity_")}
    t = _as_text(slim, table_max + 120)
    return t if len(t) <= table_max else t[: table_max - 1] + "…"


def pick_log_source_category(doc: dict[str, Any]) -> str:
    """
    Catégorie d’origine — windows / linux / switch / network / other.
    Utilisé pour le filtrage côté API (con4mity_ui_source) et la colonne « Source ».
    """
    hot = (doc.get("host") or {}) if isinstance(doc.get("host"), dict) else {}
    os_type = (hot.get("os") or {}) if isinstance(hot.get("os"), dict) else {}
    hos = (os_type.get("type") or os_type.get("name") or "").lower()
    if hos in ("windows", "win32nt"):
        return "windows"
    if hos in ("linux", "macos", "darwin"):
        return "linux"
    ag = (doc.get("agent") or {}) if isinstance(doc.get("agent"), dict) else {}
    an = str(ag.get("name") or ag.get("type") or "").lower()
    if "winlog" in an:
        return "windows"
    if "filebeat" in an and "winlog" not in an:
        return "linux"
    if "osquery" in an or "auditbeat" in an or "metricbeat" in an:
        return "linux"
    ds = doc.get("data_stream")
    ds_s = str(ds if not isinstance(ds, dict) else (ds or {}).get("dataset", "")).lower()
    if "windows" in ds_s or "winlog" in ds_s or "sysmon" in ds_s:
        return "windows"
    if any(x in ds_s for x in ("cisco", "fortinet", "palo", "juniper", "asa")):
        return "switch" if "switch" in ds_s or "cisco" in ds_s or "juniper" in ds_s else "network"
    et = (doc.get("event") or {}) if isinstance(doc.get("event"), dict) else {}
    if str(et.get("module") or "").lower() in ("cisco", "juniper"):
        return "switch"
    obs = (doc.get("observer") or {}) if isinstance(doc.get("observer"), dict) else {}
    odev = str(obs.get("type") or obs.get("product") or "").lower()
    if odev in ("firewall", "ids", "ips", "firewall"):
        return "network"
    for blob in (doc.get("message"), doc.get("raw_message"), doc.get("log")):
        if not isinstance(blob, str):
            continue
        u = blob[:4000].upper()
        if u.startswith("%LINK-") or u.startswith("%LINEPROTO-") or "GIGABITETH" in u or "ETH-" in u[:40]:
            return "switch"
        if "JUNIPER" in u or u.startswith("CISCO-") and "APPLIANCE" not in u[:80]:
            return "switch"
        if "FORTIGATE" in u or "PALO ALTO" in u or (u.startswith("TRAFFIC") and "PORT" in u):
            return "network"
    return "other"


def ui_envelope(doc: dict[str, Any]) -> dict[str, Any]:
    """Copie du document + champs dérivés pour le front (sans écraser l’existant)."""
    out = dict(doc)
    out["con4mity_ui_host"] = pick_host(doc)
    out["con4mity_ui_severity"] = pick_severity(doc)
    out["con4mity_ui_message"] = pick_message(doc)
    out["con4mity_ui_source"] = pick_log_source_category(doc)
    ts = pick_timestamp_raw(doc)
    if ts:
        out["con4mity_ui_timestamp"] = ts
    return out


def aggregate_top_ips(docs: list[dict[str, Any]], limit: int = 8) -> list[dict[str, Any]]:
    """Compte les IPv4 présentes dans les messages (hors loopback)."""
    c: Counter[str] = Counter()
    for d in docs:
        for blob in (d.get("log"), d.get("message"), d.get("raw_message")):
            if not isinstance(blob, str):
                continue
            for ip in _IP.findall(blob):
                if ip.startswith("127.") or ip == "0.0.0.0":
                    continue
                c[ip] += 1
    return [{"ip": ip, "count": n} for ip, n in c.most_common(limit)]
