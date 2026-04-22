-- Préférences interface par utilisateur (thème, langue, ordre des blocs dashboard)
-- psql -h HOTE -U con4mity -d con4mity -f 007_user_preferences.sql

CREATE TABLE IF NOT EXISTS user_preferences (
  user_id     INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
  updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  theme       VARCHAR(16) NOT NULL DEFAULT 'dark',
  locale      VARCHAR(8),
  compact_mode BOOLEAN NOT NULL DEFAULT FALSE,
  dashboard   JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_user_preferences_updated
  ON user_preferences (updated_at DESC);

COMMENT ON TABLE user_preferences IS 'Préférences UI (synchronisées multi-appareils) — thème, locale, ordre des panneaux logs';
