-- Con4mity — table « alerts » (base pour /api/alerts, stats, graphique 30j)
-- À lancer sur la base PostgreSQL (ex. con4mity) si la table n’existe pas ou est incomplète.
--
--   psql -h HOTE -U con4mity -d con4mity -f 006_alerts_bootstrap.sql
--
-- Ensuite (si ce n’est pas déjà fait) : 001_alerts_updated_at.sql, 004_alerts_status_note.sql
-- Puis enchaîner les alertes (ELK, règle custom, import) — ou insérer des lignes de test.

CREATE TABLE IF NOT EXISTS alerts (
  id           BIGSERIAL PRIMARY KEY,
  created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at   TIMESTAMPTZ,
  rule_name    TEXT,
  severity     TEXT,
  host         TEXT,
  description  TEXT,
  status       TEXT NOT NULL DEFAULT 'new',
  log_ids      TEXT,
  status_note  TEXT,
  last_actor   TEXT
);

-- Index utiles listes + agrégations
CREATE INDEX IF NOT EXISTS idx_alerts_created_at ON alerts (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_alerts_status ON alerts (status);
CREATE INDEX IF NOT EXISTS idx_alerts_severity ON alerts (severity);

COMMENT ON TABLE alerts IS 'Alertes opérateur (SIEM) — alimentation par moteur de détection / import';

-- Donnée de test optionnelle (décommenter) :
-- INSERT INTO alerts (rule_name, severity, host, description, status)
-- VALUES ('test.rule', 'high', 'srv-test', 'Exemple d’alerte de démonstration', 'new');
