-- =============================================================================
-- Con4mity — compte de connexion dashboard (DEV / labo uniquement)
-- À exécuter sur PostgreSQL (base con4mity) :
--   psql -h <PG_HOST> -U con4mity -d con4mity -f 002_seed_admin_login.sql
--
-- Crée un compte « admin ». Le hash ci-dessous est un EXEMPLE de labo :
-- générer un nouveau hash bcrypt et changer le mot de passe avant toute mise en service.
-- Ne jamais committer de secret en clair.
-- =============================================================================

ALTER TABLE alerts
  ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ;

UPDATE alerts SET updated_at = created_at WHERE updated_at IS NULL;

DELETE FROM users WHERE username = 'admin';

-- Remplacer ce hash par un hash bcrypt généré localement avant la prod.
INSERT INTO users (username, password_hash, role)
VALUES (
  'admin',
  '$2b$12$REPLACE_WITH_YOUR_OWN_BCRYPT_HASH____________________________',
  'admin'
);
