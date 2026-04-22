-- Journal des actions opérateur / playbooks (léger, adapté Raspberry Pi)
CREATE TABLE IF NOT EXISTS operator_activity (
    id SERIAL PRIMARY KEY,
    username TEXT NOT NULL,
    action_key TEXT NOT NULL,
    detail TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_operator_activity_created
    ON operator_activity (created_at DESC);
