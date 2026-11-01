-- Applied through Supabase SQL on 2026-10-24. No runtime access granted.
CREATE SCHEMA IF NOT EXISTS agentvault;
REVOKE ALL ON SCHEMA agentvault FROM PUBLIC;
SET search_path=agentvault,pg_catalog;

CREATE TABLE IF NOT EXISTS av_vaults (
 id TEXT PRIMARY KEY, token_hash TEXT NOT NULL, created_at BIGINT NOT NULL,
 expires_at BIGINT NOT NULL DEFAULT 0, version BIGINT NOT NULL DEFAULT 0,
 quota_bytes BIGINT NOT NULL, terms_version TEXT NOT NULL, deleted_at BIGINT NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS av_checkpoints (
 vault_id TEXT NOT NULL REFERENCES av_vaults(id), version BIGINT NOT NULL,
 created_at BIGINT NOT NULL, byte_count BIGINT NOT NULL, digest TEXT NOT NULL,
 encrypted BYTEA NOT NULL, PRIMARY KEY(vault_id,version));
CREATE TABLE IF NOT EXISTS av_orders (
 reference TEXT PRIMARY KEY, vault_id TEXT NOT NULL REFERENCES av_vaults(id),
 provider_id TEXT UNIQUE, amount TEXT NOT NULL, state TEXT NOT NULL,
 created_at BIGINT NOT NULL, granted_at BIGINT NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS av_limits (bucket TEXT PRIMARY KEY, count BIGINT NOT NULL);
CREATE TABLE IF NOT EXISTS av_audit (
 id TEXT PRIMARY KEY, vault_id TEXT NOT NULL, event TEXT NOT NULL, created_at BIGINT NOT NULL);
CREATE INDEX IF NOT EXISTS av_orders_vault ON av_orders(vault_id);
CREATE INDEX IF NOT EXISTS av_audit_created ON av_audit(created_at);
ALTER TABLE av_vaults ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON av_vaults FROM PUBLIC,anon,authenticated;
ALTER TABLE av_checkpoints ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON av_checkpoints FROM PUBLIC,anon,authenticated;
ALTER TABLE av_orders ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON av_orders FROM PUBLIC,anon,authenticated;
ALTER TABLE av_limits ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON av_limits FROM PUBLIC,anon,authenticated;
ALTER TABLE av_audit ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON av_audit FROM PUBLIC,anon,authenticated;
