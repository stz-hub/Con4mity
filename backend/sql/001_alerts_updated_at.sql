-- À exécuter sur PostgreSQL (CT 104), une fois, avec un user qui a les droits sur con4mity.
-- Exemple : psql -h 192.168.0.104 -U con4mity -d con4mity -f 001_alerts_updated_at.sql

ALTER TABLE alerts
  ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ;

-- Optionnel : backfill pour les lignes existantes
UPDATE alerts SET updated_at = created_at WHERE updated_at IS NULL;
