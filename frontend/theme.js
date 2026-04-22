/**
 * Thème clair / sombre — localStorage con4mity_theme (dark | light).
 * Crée le bouton #theme-toggle avant #logout si absent.
 */
(function () {
  const KEY = "con4mity_theme";

  function apply() {
    const th = localStorage.getItem(KEY) || "dark";
    if (window.Con4mityPreferences && typeof window.Con4mityPreferences.applyThemeFromValue === "function") {
      window.Con4mityPreferences.applyThemeFromValue(th);
      return;
    }
    if (th === "system") {
      const dark = window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches;
      document.documentElement.setAttribute("data-theme", dark ? "dark" : "light");
    } else {
      document.documentElement.setAttribute("data-theme", th);
    }
    const b = document.getElementById("theme-toggle");
    if (b) {
      const eff = document.documentElement.getAttribute("data-theme") || "dark";
      b.textContent = eff === "dark" ? "☀" : "☽";
      b.setAttribute("data-theme-current", eff);
    }
  }

  function inject() {
    const logout = document.getElementById("logout");
    if (!logout || document.getElementById("theme-toggle")) return;
    const b = document.createElement("button");
    b.type = "button";
    b.id = "theme-toggle";
    b.className = "btn btn--ghost";
    b.setAttribute("aria-label", "Theme");
    b.setAttribute("data-i18n-title", "theme.toggle");
    logout.parentNode.insertBefore(b, logout);
  }

  function wire() {
    const b = document.getElementById("theme-toggle");
    if (!b || b.dataset.wired) return;
    b.dataset.wired = "1";
    b.addEventListener("click", function () {
      const cur = localStorage.getItem(KEY) || "dark";
      const eff = cur === "system" ? (document.documentElement.getAttribute("data-theme") || "dark") : cur;
      const n = eff === "dark" ? "light" : "dark";
      localStorage.setItem(KEY, n);
      document.documentElement.removeAttribute("data-theme-mode");
      apply();
      window.dispatchEvent(new CustomEvent("con4mity-theme", { detail: { theme: n } }));
      if (window.Con4mityPreferences && typeof getToken === "function" && getToken() && typeof window.Con4mityPreferences.save === "function") {
        window.Con4mityPreferences.save({ theme: n }).catch(function () {});
      }
    });
  }

  function run() {
    inject();
    apply();
    wire();
    if (window.CON4MITY_I18N && typeof window.CON4MITY_I18N.applyTranslations === "function") {
      window.CON4MITY_I18N.applyTranslations();
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", run);
  } else {
    run();
  }
  window.addEventListener("con4mity-lang", apply);
})();
