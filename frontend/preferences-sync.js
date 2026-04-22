/**
 * Synchronisation des préférences utilisateur (GET /api/me/preferences) — prod.
 * - Thème (dark | light | system) + localStorage con4mity_theme
 * - Locale (fr|en|es) + con4mity_lang + événement con4mity-lang
 * - Mode compact (classe body layout-compact)
 * - Cache local con4mity_prefs_cache (fallback hors-ligne)
 * - Page logs : ordre des blocs (#dashboard-stack), graphiques / WS par défaut
 */
(function () {
  var CACHE_KEY = "con4mity_prefs_cache";
  var THEME_KEY = "con4mity_theme";
  var LANG_KEY = "con4mity_lang";

  function setChartsVisibility(on) {
    var cw = document.getElementById("charts-wrap");
    var mg = document.getElementById("block-maps");
    if (cw) cw.style.display = on ? "" : "none";
    if (mg) mg.style.display = on ? "" : "none";
    var wch = document.getElementById("w-charts");
    if (wch) wch.checked = on;
  }

  function applyLogsLayoutFromPrefs(dash) {
    if (!dash || typeof dash.logs !== "object") return;
    var lg = dash.logs;
    var root = document.getElementById("dashboard-stack");
    if (root) {
      var order = lg.panel_order || [];
      for (var i = 0; i < order.length; i++) {
        var el = root.querySelector('[data-dash-panel="' + String(order[i]) + '"]');
        if (el) el.style.order = String(i);
      }
    }
    if (Object.prototype.hasOwnProperty.call(lg, "charts_visible")) {
      setChartsVisibility(!!lg.charts_visible);
    }
    if (lg.ws_default === true) {
      var w = document.getElementById("w-ws");
      if (w) w.checked = true;
    }
  }

  function applyThemeFromValue(th) {
    var t = (th || "dark").toLowerCase();
    if (t === "system") {
      document.documentElement.removeAttribute("data-theme");
      var dark = window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches;
      document.documentElement.setAttribute("data-theme", dark ? "dark" : "light");
      document.documentElement.setAttribute("data-theme-mode", "system");
    } else {
      document.documentElement.setAttribute("data-theme", t === "light" ? "light" : "dark");
      document.documentElement.removeAttribute("data-theme-mode");
    }
    localStorage.setItem(THEME_KEY, t === "light" || t === "dark" || t === "system" ? t : "dark");
    var b = document.getElementById("theme-toggle");
    if (b) {
      var eff = document.documentElement.getAttribute("data-theme") || "dark";
      b.textContent = eff === "dark" ? "☀" : "☽";
      b.setAttribute("data-theme-current", eff);
    }
  }

  function applyLocale(loc) {
    if (!loc || !/^(fr|en|es)$/.test(loc)) return;
    try {
      localStorage.setItem(LANG_KEY, loc);
      if (window.CON4MITY_I18N && typeof window.CON4MITY_I18N.setLang === "function") {
        window.CON4MITY_I18N.setLang(loc);
      } else {
        localStorage.setItem(LANG_KEY, loc);
        window.dispatchEvent(new CustomEvent("con4mity-lang", { detail: { lang: loc } }));
      }
    } catch (_) {}
  }

  function applyCompact(on) {
    document.body.classList.toggle("layout-compact", !!on);
  }

  function applyLogsPagePrefs(dashboard) {
    applyLogsLayoutFromPrefs(dashboard || {});
  }

  function applyAll(p) {
    if (!p || typeof p !== "object") return;
    if (p.theme) applyThemeFromValue(p.theme);
    if (p.locale) applyLocale(p.locale);
    if (typeof p.compact_mode === "boolean") applyCompact(p.compact_mode);
    applyLogsPagePrefs(p.dashboard);
    try {
      localStorage.setItem(CACHE_KEY, JSON.stringify(p));
    } catch (_) {}
  }

  function loadCache() {
    try {
      var raw = localStorage.getItem(CACHE_KEY);
      if (!raw) return null;
      return JSON.parse(raw);
    } catch (_) {
      return null;
    }
  }

  window.Con4mityApplyLogsLayout = applyLogsLayoutFromPrefs;

  window.Con4mityPreferences = {
    pull: function () {
      if (typeof getToken !== "function" || !getToken()) {
        var c = loadCache();
        if (c) applyAll(c);
        return Promise.resolve(null);
      }
      if (typeof apiGet === "function") {
        return apiGet("/me/preferences")
          .then(function (p) {
            if (p) applyAll(p);
            return p;
          })
          .catch(function () {
            var c2 = loadCache();
            if (c2) applyAll(c2);
            return null;
          });
      }
      return Promise.resolve(null);
    },
    save: function (partial) {
      if (typeof apiPut !== "function") return Promise.reject(new Error("apiPut"));
      return apiPut("/me/preferences", partial).then(function (p) {
        applyAll(p);
        return p;
      });
    },
    applyThemeFromValue: applyThemeFromValue,
    applyCompact: applyCompact,
  };

  if (window.matchMedia) {
    window
      .matchMedia("(prefers-color-scheme: dark)")
      .addEventListener("change", function () {
        var stored = localStorage.getItem(THEME_KEY) || "dark";
        if (stored === "system") applyThemeFromValue("system");
      });
  }

  function runPull() {
    if (window.Con4mityPreferences) {
      return window.Con4mityPreferences.pull();
    }
  }
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", runPull);
  } else {
    runPull();
  }
})();

