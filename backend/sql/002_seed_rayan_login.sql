-- =============================================================================
-- Con4mity — compte de connexion dashboard (DEV / labo uniquement)
-- À exécuter sur PostgreSQL CT 104, base con4mity, user con4mity :
--   psql -h 192.168.0.104 -U con4mity -d con4mity -f 002_seed_rayan_login.sql
--
-- Identifiants après exécution :
--   Utilisateur : rayan
--   Mot de passe : Con4mityDemo2026!
--
-- Changer le mot de passe en prod ; ne pas committer ce fichier sur un dépôt public.
-- =============================================================================

-- Colonne pour PATCH /api/alerts/{id} (si pas déjà fait)
ALTER TABLE alerts
  ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ;

UPDATE alerts SET updated_at = created_at WHERE updated_at IS NULL;

-- Un seul compte « rayan » : on supprime l’ancienne ligne dev puis on réinsère
DELETE FROM users WHERE username = 'rayan';

-- Hash bcrypt complet (60 car.) pour le mot de passe : Con4mityDemo2026!
INSERT INTO users (username, password_hash, role)
VALUES (
  'rayan',
  '$2b$12$iMbrUIf92DofTysmSWN5G.XF/cXWJQT2acpxlvlIuvHeTCW608dya',
  'admin'
);
