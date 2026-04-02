-- Supabase table for Finance Tracker v2 anonymous telemetry
-- Project: oetfiiatbzfydbtzozlz
-- Run this in the Supabase SQL Editor

CREATE TABLE telemetry_v2 (
  id bigserial primary key,
  created_at timestamptz default now(),
  event text not null,
  v text,
  stage text,
  result text,
  duration_bucket text,
  error_code text,
  setup_mode text,
  detected_language text,
  distribution text,
  income_source_count int,
  debt_count int,
  business_type_count int,
  custom_category_count int,
  rulepack_ids jsonb,
  cron_job_count int,
  reviewed boolean default false
);

-- Enable RLS (required for Supabase)
ALTER TABLE telemetry_v2 ENABLE ROW LEVEL SECURITY;

-- Allow anon inserts only (no read, no update, no delete)
CREATE POLICY "anon_insert_only" ON telemetry_v2
  FOR INSERT
  TO anon
  WITH CHECK (true);

-- Index for event type queries
CREATE INDEX idx_telemetry_v2_event ON telemetry_v2 (event);
CREATE INDEX idx_telemetry_v2_created ON telemetry_v2 (created_at DESC);
