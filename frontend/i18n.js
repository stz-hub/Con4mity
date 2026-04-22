/**
 * Con4mity — FR / EN / ES (localStorage con4mity_lang).
 * L’espagnol reprend l’anglais pour les clés non traduites (Object.assign).
 */
(function () {
  const STORAGE_KEY = "con4mity_lang";

  const STR = {
    fr: {
      "pageTitle.login": "Con4mity — Connexion",
      "pageTitle.dashboard": "Con4mity — Tableau de bord",
      "pageTitle.alerts": "Con4mity — Alertes",
      "pageTitle.overview": "Con4mity — Vue d'ensemble",
      "pageTitle.logs": "Con4mity — Logs",
      "pageTitle.logsDash": "Con4mity — Tableau de bord & logs",
      "pageTitle.sources": "Con4mity — Sources",
      "pageTitle.reports": "Con4mity — Rapports",
      "pageTitle.automation": "Con4mity — Automatisation",
      "login.tagline": "SIEM open source — connexion opérateur",
      "login.username": "Identifiant",
      "login.password": "Mot de passe",
      "login.submit": "Se connecter",
      "login.errorInvalid": "Identifiants invalides",
      "login.errorNetwork": "Erreur de connexion",
      "login.errorSession": "Session expirée ou non authentifié",
      "login.footer": "Espace réservé aux opérateurs autorisés.",
      "nav.overview": "Vue d'ensemble",
      "nav.logs": "Logs",
      "nav.alerts": "Alertes",
      "nav.sources": "Sources",
      "nav.reports": "Rapports",
      "nav.automation": "Automatisation",
      "nav.logout": "Déconnexion",
      "logs.mergedHint": "Vue d’ensemble et journal : page fusionnée (vue d’ensemble + flux).",
      "logs.colSource": "Source",
      "logs.viewDetail": "Voir détail",
      "logs.exportCsv": "Export CSV (audit)",
      "logs.jsonTitle": "Détail du log (JSON)",
      "logs.pageInd": "Page {p} / {n}",
      "logs.pagePrev": "Précédent",
      "logs.pageNext": "Suivant",
      "logs.volHint": "Dernier rafraîchissement",
      "logs.realtimeVolume": "Volume 24 h (OpenSearch, agrégation)",
      "logs.top5hosts": "Top 5 machines (échantillon)",
      "logs.top5rules": "Top 5 règles d’alerte (30 j.)",
      "logs.volBarTitle": "Lignes (filtre actif)",
      "logs.volPerHour": "Moyenne / h (24 h)",
      "logs.sourceAll": "Toutes",
      "logs.sourceOther": "Autre",
      "theme.toggle": "Thème clair / sombre",
      "services.title": "État des services",
      "sources.heading": "Sources de collecte",
      "sources.subtitle": "Dernière activité par hôte (OpenSearch, agrégation).",
      "sources.colHost": "Hôte",
      "sources.colLast": "Dernier log",
      "sources.colBadge": "État",
      "sources.badgeActive": "actif",
      "sources.badgeSilent": "silencieux",
      "sources.badgeDown": "stale / absent",
      "alerts.chart30d": "Alertes par jour (30 jours)",
      "alerts.linkedLogs": "Journaux liés",
      "alerts.ackComment": "Commentaire (acquittement)",
      "alerts.ackOptional": "Qui, pourquoi, actions… (optionnel)",
      "alerts.openDetail": "Détail & journaux",
      "alerts.requestNotif": "Activer notif. navigateur (critique)",
      "alerts.newCritical": "Nouvelles alertes critiques (non résolues)",
      "automation.pageIntro": "Playbooks d’orchestration léger : rappels, vérifications, journal d’audit — pas d’exécution lourde automatisée ici. Isolation, blocage, tickets : côté runbook / outils métiers.",
      "playbook.triage_credential.title": "Rotation des comptes (rappel)",
      "playbook.triage_credential.desc": "PAM, comptes de service, privilèges.",
      "playbook.isolate_host_hint.title": "Isolation d’hôte (checklist)",
      "playbook.isolate_host_hint.desc": "VLAN, pare-feu, NAC — validation réseau manuelle.",
      "playbook.escalation_ticket.title": "Ticket d’escalade",
      "playbook.escalation_ticket.desc": "Jira, GLPI, Mantis — intégration future.",
      "lang.label": "Langue",
      "dashboard.heading": "Flux des événements",
      "dashboard.subtitle": "Dernières entrées indexées dans OpenSearch",
      "dashboard.kpiNew": "Alertes « nouvelles »",
      "dashboard.kpiProgress": "En cours",
      "dashboard.kpiResolved": "Résolues",
      "dashboard.kpiTotal": "Total alertes",
      "dashboard.kpiRefresh": "Rafraîchissement auto",
      "dashboard.refresh": "Actualiser",
      "dashboard.searchPlaceholder": "Rechercher dans les messages ou hôtes…",
      "dashboard.colTime": "Date / heure",
      "dashboard.colHost": "Hôte",
      "dashboard.colSeverity": "Sévérité",
      "dashboard.colMessage": "Message",
      "dashboard.statusLoading": "Chargement…",
      "dashboard.statusLines": "{n} ligne(s) · dernière mise à jour {t}",
      "dashboard.statusError": "Erreur : {m}",
      "dashboard.noLogs": "Aucun log pour le moment.",
      "dashboard.noMatch": "Aucun résultat pour cette recherche.",
      "alerts.heading": "Centre d'alertes",
      "alerts.subtitle": "Traiter et suivre les détections",
      "alerts.filterSeverity": "Sévérité",
      "alerts.filterStatus": "Statut",
      "alerts.optAllSev": "Toutes",
      "alerts.optAllSt": "Tous",
      "alerts.colDate": "Date",
      "alerts.colRule": "Règle",
      "alerts.colHost": "Hôte",
      "alerts.colSeverity": "Sévérité",
      "alerts.colStatus": "Statut",
      "alerts.colActions": "Actions",
      "alerts.actionProgress": "Prendre en charge",
      "alerts.actionResolved": "Résolu",
      "alerts.empty": "Aucune alerte à afficher.",
      "alerts.noFilterMatch": "Aucune alerte ne correspond aux filtres.",
      "status.new": "nouvelle",
      "status.in_progress": "en cours",
      "status.resolved": "résolue",
      "severity.critical": "critical",
      "severity.high": "high",
      "severity.medium": "medium",
      "severity.low": "low",
      "overview.subtitle": "Synthèse temps réel (données légères pour matériel modeste)",
      "overview.kpiIncidents": "Incidents ouverts",
      "overview.kpiCritical": "Alertes critiques (actives)",
      "overview.kpiEvents": "Événements (échantillon 24 h)",
      "overview.kpiNetwork": "Activité récente (3 h)",
      "overview.chartTimeline": "Volume d'événements (24 h)",
      "overview.chartHosts": "Hôtes les plus actifs",
      "overview.timelineTitle": "Frise chronologique (densité)",
      "overview.mapTitle": "Carte des connexions",
      "overview.mapBody": "Les adresses IP sources sont listées à droite ; la géolocalisation peut être branchée plus tard (enrichissement léger).",
      "overview.refresh": "Rafraîchir",
      "overview.widgets": "Affichage des graphiques",
      "overview.topHosts": "Hôtes",
      "overview.topIps": "Adresses IP",
      "overview.noHosts": "Aucun hôte déduit dans l’échantillon.",
      "overview.noIps": "Aucune IPv4 détectée (hors loopback).",
      "logs.filtersTitle": "Filtres rapides",
      "logs.filterFrom": "Depuis",
      "logs.filterTo": "Jusqu'à",
      "logs.filterHost": "Machine / hôte",
      "logs.filterEvent": "Type d'événement",
      "logs.filterUser": "Utilisateur",
      "logs.applyFilters": "Appliquer",
      "logs.clearFilters": "Réinitialiser",
      "reports.subtitle": "Exports simples côté navigateur (sans charge serveur lourde).",
      "reports.exportLogs": "Exporter les derniers logs (CSV)",
      "reports.exportAlerts": "Exporter les alertes (CSV)",
      "reports.hint": "Les exports utilisent les données déjà chargées ou une requête unique.",
      "automation.subtitle": "Actions guidées et journal (style playbook léger).",
      "automation.playbooks": "Playbooks",
      "automation.run": "Exécuter",
      "automation.history": "Historique des actions",
      "automation.emptyHistory": "Aucune entrée (exécuter sql/003_operator_activity.sql sur PostgreSQL).",
      "automation.colUser": "Utilisateur",
      "automation.colAction": "Action",
      "automation.colDetail": "Détail",
      "alerts.grouped": "Vue regroupée (anti-spam)",
      "alerts.flat": "Vue détaillée",
      "alerts.countSimilar": "{n} similaires",
      "alerts.expand": "Détails",
      "alerts.investigate": "Voir les logs filtrés",
      "alerts.detailTitle": "Détail de l'alerte",
      "playbook.export_hint.title": "Exporter les indices",
      "playbook.export_hint.desc": "Redirige vers l'export CSV côté rapports.",
      "playbook.refresh_index_hint.title": "Vérifier l'indexation",
      "playbook.refresh_index_hint.desc": "Rappel de contrôle OpenSearch (aucune action destructive).",
      "playbook.notify_placeholder.title": "Notification (simulation)",
      "playbook.notify_placeholder.desc": "Aucun email envoyé — placeholder pour intégration future.",
      "nav.settings": "Paramètres",
      "pageTitle.settings": "Con4mity — Paramètres",
      "pageTitle.documentation": "Con4mity — Documentation",
      "footer.docs": "Documentation",
      "footer.tag": "Con4mity — SIEM open source",
      "doc.versionLabel": "Version de la documentation",
      "login.langHint": "Langue : réglage principal dans Paramètres après connexion.",
      "settings.intro": "Structure recommandée (cible Raspberry Pi : beaucoup d’options sont des repères d’évolution, pas encore toutes branchées au backend).",
      "settings.block.gestion": "Gestion",
      "settings.block.detection": "Détection",
      "settings.block.system": "Système",
      "settings.lang.title": "Langue de l’interface",
      "settings.lang.desc": "Français, anglais ou espagnol. Préférence stockée dans ce navigateur.",
      "settings.lang.fr": "Français",
      "settings.lang.en": "English",
      "settings.lang.es": "Español",
      "settings.users.title": "Utilisateurs & accès",
      "settings.users.desc": "Comptes, rôles (admin, analyste, lecture seule), MFA / SSO — aligné sur une vision type Microsoft Sentinel (à connecter à PostgreSQL / IdP).",
      "settings.security.title": "Sécurité",
      "settings.security.desc": "Politique de mots de passe, journal des connexions, restrictions IP / géo, clés API.",
      "settings.data.title": "Sources de données",
      "settings.data.desc": "Serveurs, pare-feu, cloud ; statut de collecte et agents — inspiration Splunk ES.",
      "settings.alerts.title": "Alertes & règles",
      "settings.alerts.desc": "Règles de détection, seuils, priorités, déduplication.",
      "settings.soar.title": "Automatisation (SOAR léger)",
      "settings.soar.desc": "Playbooks, actions (blocage IP, mail, ticket), conditions de déclenchement.",
      "settings.retention.title": "Logs & rétention",
      "settings.retention.desc": "Durée de stockage, archivage, compression, conformité (RGPD).",
      "settings.dashreports.title": "Tableaux de bord & rapports",
      "settings.dashreports.desc": "Personnalisation, modèles, planification d’envoi (email, PDF).",
      "settings.integrations.title": "Intégrations",
      "settings.integrations.desc": "EDR, antivirus, ticketing, API, webhooks.",
      "settings.notifications.title": "Notifications",
      "settings.notifications.desc": "Email, Slack, SMS ; fréquence ; types d’alertes à notifier.",
      "settings.threatintel.title": "Threat intelligence",
      "settings.threatintel.desc": "Feeds IP / domaines, mise à jour auto, priorisation.",
      "settings.system.title": "Système",
      "settings.system.desc": "CPU, stockage, mises à jour SIEM, sauvegardes, santé globale.",
      "settings.ui.title": "Interface & personnalisation",
      "settings.ui.desc": "Thème clair / sombre, organisation des widgets, préférences utilisateur.",
      "settings.status.placeholder": "À venir / configuration externe",
    },
    en: {
      "pageTitle.login": "Con4mity — Sign in",
      "pageTitle.dashboard": "Con4mity — Dashboard",
      "pageTitle.alerts": "Con4mity — Alerts",
      "pageTitle.overview": "Con4mity — Overview",
      "pageTitle.logs": "Con4mity — Logs",
      "pageTitle.logsDash": "Con4mity — Dashboard & logs",
      "pageTitle.sources": "Con4mity — Sources",
      "pageTitle.reports": "Con4mity — Reports",
      "pageTitle.automation": "Con4mity — Automation",
      "login.tagline": "Open source SIEM — operator sign-in",
      "login.username": "Username",
      "login.password": "Password",
      "login.submit": "Sign in",
      "login.errorInvalid": "Invalid username or password",
      "login.errorNetwork": "Connection error",
      "login.errorSession": "Session expired or not authenticated",
      "login.footer": "Authorized operators only.",
      "nav.overview": "Overview",
      "nav.logs": "Logs",
      "nav.alerts": "Alerts",
      "nav.sources": "Sources",
      "nav.reports": "Reports",
      "nav.automation": "Automation",
      "nav.logout": "Sign out",
      "logs.mergedHint": "Overview and log stream in one place.",
      "logs.colSource": "Source",
      "logs.viewDetail": "View details",
      "logs.exportCsv": "Export CSV (audit)",
      "logs.jsonTitle": "Log detail (JSON)",
      "logs.pageInd": "Page {p} / {n}",
      "logs.pagePrev": "Previous",
      "logs.pageNext": "Next",
      "logs.volHint": "Last refresh",
      "logs.realtimeVolume": "24h volume (OpenSearch aggregation)",
      "logs.top5hosts": "Top 5 hosts (sample)",
      "logs.top5rules": "Top 5 alert rules (30d)",
      "logs.volBarTitle": "Rows (active filter)",
      "logs.volPerHour": "Average / h (24h)",
      "logs.sourceAll": "All",
      "logs.sourceOther": "Other",
      "theme.toggle": "Light / dark theme",
      "services.title": "Service health",
      "sources.heading": "Ingestion sources",
      "sources.subtitle": "Last log time per host (OpenSearch).",
      "sources.colHost": "Host",
      "sources.colLast": "Last log",
      "sources.colBadge": "State",
      "sources.badgeActive": "active",
      "sources.badgeSilent": "silent",
      "sources.badgeDown": "stale / down",
      "alerts.chart30d": "Alerts per day (30 days)",
      "alerts.linkedLogs": "Linked logs",
      "alerts.ackComment": "Acknowledgment comment",
      "alerts.ackOptional": "Who, why, next steps (optional)",
      "alerts.openDetail": "Detail & logs",
      "alerts.requestNotif": "Enable browser notifications (critical)",
      "alerts.newCritical": "New open critical alerts",
      "automation.pageIntro": "Light SOAR playbooks: checklists, reminders, audit log — not heavy remote execution here. Isolation, blocking, tickets: use your runbooks and tools.",
      "playbook.triage_credential.title": "Account rotation (reminder)",
      "playbook.triage_credential.desc": "PAM, service accounts, privileges.",
      "playbook.isolate_host_hint.title": "Host isolation (checklist)",
      "playbook.isolate_host_hint.desc": "VLAN, firewall, NAC — manual network team validation.",
      "playbook.escalation_ticket.title": "Escalation ticket",
      "playbook.escalation_ticket.desc": "Jira, GLPI, Mantis — future integration.",
      "lang.label": "Language",
      "dashboard.heading": "Event stream",
      "dashboard.subtitle": "Latest records indexed in OpenSearch",
      "dashboard.kpiNew": "New alerts",
      "dashboard.kpiProgress": "In progress",
      "dashboard.kpiResolved": "Resolved",
      "dashboard.kpiTotal": "Total alerts",
      "dashboard.kpiRefresh": "Auto-refresh",
      "dashboard.refresh": "Refresh now",
      "dashboard.searchPlaceholder": "Search messages or hosts…",
      "dashboard.colTime": "Date / time",
      "dashboard.colHost": "Host",
      "dashboard.colSeverity": "Severity",
      "dashboard.colMessage": "Message",
      "dashboard.statusLoading": "Loading…",
      "dashboard.statusLines": "{n} row(s) · last update {t}",
      "dashboard.statusError": "Error: {m}",
      "dashboard.noLogs": "No logs yet.",
      "dashboard.noMatch": "No results match your search.",
      "alerts.heading": "Alert queue",
      "alerts.subtitle": "Triage and track detections",
      "alerts.filterSeverity": "Severity",
      "alerts.filterStatus": "Status",
      "alerts.optAllSev": "All",
      "alerts.optAllSt": "All",
      "alerts.colDate": "Date",
      "alerts.colRule": "Rule",
      "alerts.colHost": "Host",
      "alerts.colSeverity": "Severity",
      "alerts.colStatus": "Status",
      "alerts.colActions": "Actions",
      "alerts.actionProgress": "Acknowledge",
      "alerts.actionResolved": "Resolve",
      "alerts.empty": "No alerts to display.",
      "alerts.noFilterMatch": "No alerts match the current filters.",
      "status.new": "new",
      "status.in_progress": "in progress",
      "status.resolved": "resolved",
      "severity.critical": "critical",
      "severity.high": "high",
      "severity.medium": "medium",
      "severity.low": "low",
      "overview.subtitle": "Real-time summary (lightweight for small hardware)",
      "overview.kpiIncidents": "Open incidents",
      "overview.kpiCritical": "Critical alerts (active)",
      "overview.kpiEvents": "Events (24h sample)",
      "overview.kpiNetwork": "Recent activity (3h)",
      "overview.chartTimeline": "Event volume (24h)",
      "overview.chartHosts": "Busiest hosts",
      "overview.timelineTitle": "Event timeline (density)",
      "overview.mapTitle": "Connection map",
      "overview.mapBody": "Source IPs are listed on the right; geo-enrichment can be added later.",
      "overview.refresh": "Refresh",
      "overview.widgets": "Chart visibility",
      "overview.topHosts": "Hosts",
      "overview.topIps": "IP addresses",
      "overview.noHosts": "No host inferred from the sample.",
      "overview.noIps": "No IPv4 detected (excluding loopback).",
      "logs.filtersTitle": "Quick filters",
      "logs.filterFrom": "From",
      "logs.filterTo": "To",
      "logs.filterHost": "Host",
      "logs.filterEvent": "Event type",
      "logs.filterUser": "User",
      "logs.applyFilters": "Apply",
      "logs.clearFilters": "Reset",
      "reports.subtitle": "Lightweight browser-side exports.",
      "reports.exportLogs": "Export latest logs (CSV)",
      "reports.exportAlerts": "Export alerts (CSV)",
      "reports.hint": "Exports use loaded data or a single API request.",
      "automation.subtitle": "Guided actions and audit trail (light playbooks).",
      "automation.playbooks": "Playbooks",
      "automation.run": "Run",
      "automation.history": "Action history",
      "automation.emptyHistory": "No entries yet (run sql/003_operator_activity.sql on PostgreSQL).",
      "automation.colUser": "User",
      "automation.colAction": "Action",
      "automation.colDetail": "Detail",
      "alerts.grouped": "Grouped view (anti-spam)",
      "alerts.flat": "Detailed view",
      "alerts.countSimilar": "{n} similar",
      "alerts.expand": "Details",
      "alerts.investigate": "Open filtered logs",
      "alerts.detailTitle": "Alert detail",
      "playbook.export_hint.title": "Export hints",
      "playbook.export_hint.desc": "Points you to CSV export on Reports.",
      "playbook.refresh_index_hint.title": "Check indexing",
      "playbook.refresh_index_hint.desc": "OpenSearch health reminder (non-destructive).",
      "playbook.notify_placeholder.title": "Notification (simulated)",
      "playbook.notify_placeholder.desc": "No email sent — future integration hook.",
      "nav.settings": "Settings",
      "pageTitle.settings": "Con4mity — Settings",
      "pageTitle.documentation": "Con4mity — Documentation",
      "footer.docs": "Documentation",
      "footer.tag": "Con4mity — open source SIEM",
      "doc.versionLabel": "Documentation version",
      "login.langHint": "Language: main control is in Settings after sign-in.",
      "settings.intro": "Recommended layout (Raspberry Pi target: many items are roadmap placeholders until wired to the backend).",
      "settings.block.gestion": "Management",
      "settings.block.detection": "Detection",
      "settings.block.system": "System",
      "settings.lang.title": "Interface language",
      "settings.lang.desc": "French, English or Spanish. Preference stored in this browser.",
      "settings.lang.fr": "French",
      "settings.lang.en": "English",
      "settings.lang.es": "Spanish",
      "settings.users.title": "Users & access",
      "settings.users.desc": "Accounts, roles (admin, analyst, read-only), MFA / SSO — Microsoft Sentinel-style (to connect to PostgreSQL / IdP).",
      "settings.security.title": "Security",
      "settings.security.desc": "Password policy, sign-in log, IP / geo restrictions, API keys.",
      "settings.data.title": "Data sources",
      "settings.data.desc": "Servers, firewalls, cloud; collection status and agents — Splunk ES-like.",
      "settings.alerts.title": "Alerts & rules",
      "settings.alerts.desc": "Detection rules, thresholds, priorities, deduplication.",
      "settings.soar.title": "Automation (light SOAR)",
      "settings.soar.desc": "Playbooks, actions (block IP, email, ticket), trigger conditions.",
      "settings.retention.title": "Logs & retention",
      "settings.retention.desc": "Retention, archiving, compression, compliance (GDPR).",
      "settings.dashreports.title": "Dashboards & reports",
      "settings.dashreports.desc": "Customization, templates, scheduled delivery (email, PDF).",
      "settings.integrations.title": "Integrations",
      "settings.integrations.desc": "EDR, AV, ticketing, API, webhooks.",
      "settings.notifications.title": "Notifications",
      "settings.notifications.desc": "Email, Slack, SMS; frequency; which alert types to notify.",
      "settings.threatintel.title": "Threat intelligence",
      "settings.threatintel.desc": "IP/domain feeds, auto-update, prioritization.",
      "settings.system.title": "System",
      "settings.system.desc": "CPU, storage, SIEM updates, backups, global health.",
      "settings.ui.title": "UI & personalization",
      "settings.ui.desc": "Light/dark theme, widget layout, user preferences.",
      "settings.status.placeholder": "Coming soon / external configuration",
    },
  };

  STR.es = Object.assign({}, STR.en, {
    "nav.settings": "Ajustes",
    "pageTitle.settings": "Con4mity — Ajustes",
    "pageTitle.documentation": "Con4mity — Documentación",
    "footer.docs": "Documentación",
    "footer.tag": "Con4mity — SIEM de código abierto",
    "login.langHint": "Idioma: el control principal está en Ajustes tras iniciar sesión.",
    "settings.intro": "Estructura recomendada (objetivo Raspberry Pi: muchas opciones son hoja de ruta hasta conectarlas al backend).",
    "settings.block.gestion": "Gestión",
    "settings.block.detection": "Detección",
    "settings.block.system": "Sistema",
    "settings.lang.title": "Idioma de la interfaz",
    "settings.lang.desc": "Francés, inglés o español. Preferencia guardada en este navegador.",
    "settings.lang.fr": "Francés",
    "settings.lang.en": "Inglés",
    "settings.lang.es": "Español",
    "settings.users.title": "Usuarios y acceso",
    "settings.users.desc": "Cuentas, roles (admin, analista, solo lectura), MFA / SSO — visión tipo Microsoft Sentinel.",
    "settings.security.title": "Seguridad",
    "settings.security.desc": "Política de contraseñas, registro de accesos, restricciones IP / geo, claves API.",
    "settings.data.title": "Fuentes de datos",
    "settings.data.desc": "Servidores, cortafuegos, nube; estado de recolección y agentes.",
    "settings.alerts.title": "Alertas y reglas",
    "settings.alerts.desc": "Reglas de detección, umbrales, prioridades, deduplicación.",
    "settings.soar.title": "Automatización (SOAR ligero)",
    "settings.soar.desc": "Playbooks, acciones (bloquear IP, correo, ticket), condiciones de disparo.",
    "settings.retention.title": "Logs y retención",
    "settings.retention.desc": "Retención, archivo, compresión, cumplimiento (RGPD).",
    "settings.dashreports.title": "Cuadros de mando e informes",
    "settings.dashreports.desc": "Personalización, plantillas, envío programado (correo, PDF).",
    "settings.integrations.title": "Integraciones",
    "settings.integrations.desc": "EDR, antivirus, ticketing, API, webhooks.",
    "settings.notifications.title": "Notificaciones",
    "settings.notifications.desc": "Correo, Slack, SMS; frecuencia; tipos de alerta a notificar.",
    "settings.threatintel.title": "Threat intelligence",
    "settings.threatintel.desc": "Feeds IP / dominios, actualización automática, priorización.",
    "settings.system.title": "Sistema",
    "settings.system.desc": "CPU, almacenamiento, actualizaciones del SIEM, copias de seguridad, salud global.",
    "settings.ui.title": "Interfaz y personalización",
    "settings.ui.desc": "Tema claro / oscuro, disposición de widgets, preferencias de usuario.",
    "settings.status.placeholder": "Próximamente / configuración externa",
    "nav.overview": "Resumen",
    "nav.logs": "Registros",
    "nav.sources": "Fuentes",
    "nav.alerts": "Alertas",
    "nav.reports": "Informes",
    "nav.automation": "Automatización",
    "nav.logout": "Cerrar sesión",
    "doc.versionLabel": "Versión de la documentación",
    "overview.topHosts": "Hosts",
    "overview.topIps": "Direcciones IP",
    "overview.noHosts": "Ningún host deducido en la muestra.",
    "overview.noIps": "Ninguna IPv4 detectada (sin loopback).",
  });

  function getLang() {
    const v = (localStorage.getItem(STORAGE_KEY) || "fr").toLowerCase();
    if (v === "en" || v === "es") return v;
    return "fr";
  }

  function setLang(lang) {
    const next = lang === "en" || lang === "es" ? lang : "fr";
    localStorage.setItem(STORAGE_KEY, next);
    applyTranslations();
    syncLangSelects();
    window.dispatchEvent(new CustomEvent("con4mity-lang", { detail: { lang: next } }));
  }

  function t(key, vars) {
    const lang = getLang();
    let s = (STR[lang] && STR[lang][key]) || STR.en[key] || STR.fr[key] || key;
    if (vars && typeof vars === "object") {
      Object.keys(vars).forEach((k) => {
        s = s.replace(`{${k}}`, String(vars[k]));
      });
    }
    return s;
  }

  function applyTranslations() {
    const lang = getLang();
    document.documentElement.lang = lang;

    function line(k) {
      return (STR[lang] && STR[lang][k]) || STR.en[k] || STR.fr[k] || "";
    }

    document.querySelectorAll("[data-i18n]").forEach((el) => {
      const key = el.getAttribute("data-i18n");
      if (key) {
        const text = line(key);
        if (text) el.textContent = text;
      }
    });

    document.querySelectorAll("[data-i18n-placeholder]").forEach((el) => {
      const key = el.getAttribute("data-i18n-placeholder");
      if (key) {
        const text = line(key);
        if (text) el.placeholder = text;
      }
    });

    document.querySelectorAll("[data-i18n-title]").forEach((el) => {
      const key = el.getAttribute("data-i18n-title");
      if (key) {
        const text = line(key);
        if (text) el.title = text;
      }
    });

    const titleKey = document.body && document.body.getAttribute("data-page-title-key");
    if (titleKey) document.title = t(titleKey);

    document.querySelectorAll("[data-i18n-opt]").forEach((el) => {
      const key = el.getAttribute("data-i18n-opt");
      if (key) {
        const text = line(key);
        if (text) el.textContent = text;
      }
    });
  }

  function syncLangSelects() {
    const lang = getLang();
    document.querySelectorAll(".lang-select").forEach((sel) => {
      if (sel && sel.tagName === "SELECT") {
        sel.value = lang;
      }
    });
  }

  function wireLangSelects() {
    document.querySelectorAll(".lang-select").forEach((sel) => {
      if (sel.dataset.i18nWired) return;
      sel.dataset.i18nWired = "1";
      sel.addEventListener("change", () => setLang(sel.value));
    });
  }

  function initI18n() {
    wireLangSelects();
    applyTranslations();
    syncLangSelects();
  }

  if (document.body) {
    initI18n();
  } else {
    document.addEventListener("DOMContentLoaded", initI18n);
  }

  window.CON4MITY_I18N = {
    t,
    getLang,
    setLang,
    initI18n,
    applyTranslations,
    syncLangSelects,
    wireLangSelects,
  };
  window.t = t;
})();
