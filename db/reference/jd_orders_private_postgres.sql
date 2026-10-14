-- Reference schema ONLY. Not applied to any database.
-- Deploy with a privileged server-side migration after explicit project selection.
-- Keep this schema outside Supabase exposed API schemas.
BEGIN;
CREATE SCHEMA IF NOT EXISTS agentbroker_private;
REVOKE ALL ON SCHEMA agentbroker_private FROM PUBLIC, anon, authenticated;
CREATE TABLE IF NOT EXISTS agentbroker_private.jd_orders (
  id uuid PRIMARY KEY,
  status text NOT NULL DEFAULT 'new'
    CHECK (status IN ('new','payment_pending','paid','in_review',
                     'ready_for_delivery','delivered','cancelled','refunded')),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  version bigint NOT NULL DEFAULT 0 CHECK (version >= 0),
  payment_reference text UNIQUE,
  delivery_reference text
);
CREATE TABLE IF NOT EXISTS agentbroker_private.jd_order_events (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  order_id uuid NOT NULL REFERENCES agentbroker_private.jd_orders(id),
  previous_status text NOT NULL,
  next_status text NOT NULL,
  occurred_at timestamptz NOT NULL DEFAULT now(),
  actor_type text NOT NULL CHECK (actor_type IN ('system','operator','payment_webhook')),
  event_key text NOT NULL UNIQUE
);
ALTER TABLE agentbroker_private.jd_orders ENABLE ROW LEVEL SECURITY;
ALTER TABLE agentbroker_private.jd_order_events ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON ALL TABLES IN SCHEMA agentbroker_private FROM PUBLIC, anon, authenticated;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA agentbroker_private FROM PUBLIC, anon, authenticated;
COMMIT;
