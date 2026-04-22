/**
 * Champs log pour l’UI — aligné sur backend/log_normalization.py (con4mity_ui_*).
 */
(function (global) {
  "use strict";

  function pickTime(row) {
    return (
      row.con4mity_ui_timestamp ||
      row["@timestamp"] ||
      row.received_at ||
      row.timestamp ||
      "—"
    );
  }

  function pickHost(row) {
    if (row.con4mity_ui_host && row.con4mity_ui_host !== "—") return row.con4mity_ui_host;
    const h = row.host;
    if (h && typeof h === "object" && (h.name || h.hostname)) return String(h.name || h.hostname);
    if (typeof h === "string" && h.trim()) return h.trim();
    if (row["host.name"] && String(row["host.name"]).trim()) return String(row["host.name"]).trim();
    const ag = row.agent;
    if (ag && typeof ag === "object" && ag.hostname) return String(ag.hostname);
    return "—";
  }

  function pickSeverity(row) {
    if (row.con4mity_ui_severity) return String(row.con4mity_ui_severity).toLowerCase();
    if (row.severity) return String(row.severity).toLowerCase();
    const lg = row.log;
    if (lg && typeof lg === "object" && lg.level) return String(lg.level).toLowerCase();
    if (row.level) return String(row.level).toLowerCase();
    return "info";
  }

  function pickSource(row) {
    if (row.con4mity_ui_source) {
      const s = String(row.con4mity_ui_source);
      if (s === "linux") return "Linux / Unix";
      if (s === "windows") return "Windows";
      if (s === "switch") return "Switch";
      if (s === "network") return "Réseau / FW";
    }
    return String(row.con4mity_ui_source || "—");
  }

  function pickMessage(row) {
    if (row.con4mity_ui_message) return row.con4mity_ui_message;
    if (row.message && String(row.message).trim()) return String(row.message).trim();
    if (row.raw_message && String(row.raw_message).trim()) return String(row.raw_message).trim();
    if (row["event.original"] && String(row["event.original"]).trim()) return String(row["event.original"]).trim();
    if (typeof row.log === "string" && row.log.trim()) return row.log.trim();
    try {
      const slim = { ...row };
      delete slim.con4mity_ui_host;
      delete slim.con4mity_ui_severity;
      delete slim.con4mity_ui_message;
      delete slim.con4mity_ui_timestamp;
      const s = JSON.stringify(slim);
      return s.length > 200 ? s.slice(0, 200) + "…" : s;
    } catch (_) {
      return "—";
    }
  }

  function severityPillClass(sev) {
    const s = String(sev || "").toLowerCase();
    if (s === "critical" || s === "emergency" || s === "alert") return "pill pill--crit";
    if (s === "high" || s === "error") return "pill pill--high";
    if (s === "medium" || s === "warning") return "pill pill--med";
    if (s === "low" || s === "notice") return "pill pill--info";
    if (s === "info" || s === "informational" || s === "debug") return "pill pill--muted";
    return "pill pill--muted";
  }

  global.Con4mityLogFields = {
    pickTime,
    pickHost,
    pickSource,
    pickSeverity,
    pickMessage,
    severityPillClass,
  };
})(typeof window !== "undefined" ? window : globalThis);
