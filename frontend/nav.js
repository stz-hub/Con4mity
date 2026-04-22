/**
 * Con4mity — liens de navigation (remplit #main-nav-links).
 * data-nav-active sur <body> : logs | alerts | sources | reports | automation | settings
 */
(function () {
  const PAGES = [
    { id: "overview", href: "logs.html#section-overview", i18n: "nav.overview" },
    { id: "logs", href: "logs.html#section-logs", i18n: "nav.logs" },
    { id: "alerts", href: "alerts.html", i18n: "nav.alerts" },
    { id: "sources", href: "sources.html", i18n: "nav.sources" },
    { id: "reports", href: "reports.html", i18n: "nav.reports" },
    { id: "automation", href: "automation.html", i18n: "nav.automation" },
    { id: "settings", href: "settings.html", i18n: "nav.settings" },
  ];

  function renderNav() {
    const el = document.getElementById("main-nav-links");
    if (!el) return;
    const active = document.body.getAttribute("data-nav-active") || "overview";
    el.innerHTML = PAGES.map((p) => {
      const cls = p.id === active ? "navlink active" : "navlink";
      return `<a class="${cls}" href="${p.href}" data-i18n="${p.i18n}"></a>`;
    }).join("");
    if (window.CON4MITY_I18N && typeof window.CON4MITY_I18N.applyTranslations === "function") {
      window.CON4MITY_I18N.applyTranslations();
    }
  }

  function run() {
    renderNav();
    window.addEventListener("con4mity-lang", renderNav);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", run);
  } else {
    run();
  }
})();
