-- Journal de connexions, clés API, politique (Sécurité — production)
-- Exécuter: psql $DATABASE_URL -f 005_security_production.sql

CREATE TABLE IF NOT EXISTS login_events (
  id         BIGSERIAL PRIMARY KEY,
  ts         TIMESTAMPTZ NOT NULL DEFAULT now(),
  username   TEXT,
  user_id    INTEGER REFERENCES users(id) ON DELETE SET NULL,
  success    BOOLEAN NOT NULL,
  reason     TEXT,
  ip         TEXT,
  user_agent TEXT,
  geo        TEXT
);

CREATE INDEX IF NOT EXISTS idx_login_events_ts
  ON login_events (ts DESC);
CREATE INDEX IF NOT EXISTS idx_login_events_user
  ON login_events (user_id, ts DESC) WHERE user_id IS NOT NULL;

-- Clés API: secret affiché une seule fois; stocker uniquement le hash
CREATE TABLE IF NOT EXISTS api_keys (
  id         BIGSERIAL PRIMARY KEY,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  name       TEXT,
  key_hash   TEXT NOT NULL,
  key_prefix TEXT NOT NULL,
  last_used_at TIMESTAMPTZ,
  revoked    BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_api_keys_hash
  ON api_keys (key_hash) WHERE NOT revoked;
CREATE INDEX IF NOT EXISTS idx_api_keys_user
  ON api_keys (user_id, created_at DESC);

-- Politique mots de passe (une ligne) — surcharge des variables d'env quand l'admin l'enregistre
CREATE TABLE IF NOT EXISTS security_policy (
  id          SMALLINT PRIMARY KEY DEFAULT 1 CHECK (id = 1),
  updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  min_length            INTEGER NOT NULL DEFAULT 12,
  require_uppercase     BOOLEAN NOT NULL DEFAULT TRUE,
  require_lowercase     BOOLEAN NOT NULL DEFAULT TRUE,
  require_digit         BOOLEAN NOT NULL DEFAULT TRUE,
  require_special       BOOLEAN NOT NULL DEFAULT FALSE
);

INSERT INTO security_policy (id) VALUES (1) ON CONFLICT (id) DO NOTHING;

COMMENT ON TABLE login_events IS 'Journal des tentatives de connexion (production)';
COMMENT ON TABLE api_keys IS 'Clés API hachées — en-tête X-API-Key';
COMMENT ON TABLE security_policy IS 'Politique mots de passe (admin)';
