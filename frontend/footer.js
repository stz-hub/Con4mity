/**
 * Con4mity — pied de page (lien documentation + tag).
 * Conteneur : #app-footer (placé en bas de chaque page).
 */
(function () {
  var DOC_VERSION = "1.2.1";

  function renderFooter() {
    var el = document.getElementById("app-footer");
    if (!el) return;
    el.innerHTML =
      '<footer class="site-footer">' +
      '<a href="documentation.html" class="site-footer__link" data-i18n="footer.docs">Documentation</a>' +
      '<span class="site-footer__sep"> · </span>' +
      '<span class="site-footer__tag" data-i18n="footer.tag">Con4mity</span>' +
      '<span class="site-footer__sep"> · </span>' +
      '<span class="site-footer__ver">doc v' +
      DOC_VERSION +
      "</span>" +
      "</footer>";
    if (window.CON4MITY_I18N && typeof window.CON4MITY_I18N.applyTranslations === "function") {
      window.CON4MITY_I18N.applyTranslations();
    }
  }

  function run() {
    renderFooter();
    window.addEventListener("con4mity-lang", renderFooter);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", run);
  } else {
    run();
  }
})();
