-- Notes d’acquittement (qui / pourquoi) sur les alertes
-- psql: \i 004_alerts_status_note.sql

ALTER TABLE alerts
  ADD COLUMN IF NOT EXISTS status_note TEXT,
  ADD COLUMN IF NOT EXISTS last_actor VARCHAR(120);

COMMENT ON COLUMN alerts.status_note IS 'Dernier commentaire opérateur (acquittement, résolution)';
COMMENT ON COLUMN alerts.last_actor IS 'Dernier utilisateur ayant modifié le statut';
