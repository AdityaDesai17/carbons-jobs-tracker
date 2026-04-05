-- Run this in Supabase Dashboard → SQL Editor → New Query

CREATE TABLE searches (
  id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id    UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  job_title  TEXT NOT NULL,
  location   TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE jobs (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  search_id   UUID NOT NULL REFERENCES searches(id) ON DELETE CASCADE,
  user_id     UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  external_id TEXT NOT NULL,
  title       TEXT,
  company     TEXT,
  location    TEXT,
  site        TEXT,
  job_url     TEXT,
  queried_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  applied     BOOLEAN NOT NULL DEFAULT FALSE,
  UNIQUE(search_id, external_id)
);

-- Row Level Security: each user only sees their own data
ALTER TABLE searches ENABLE ROW LEVEL SECURITY;
ALTER TABLE jobs     ENABLE ROW LEVEL SECURITY;

CREATE POLICY "searches_select" ON searches FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY "searches_insert" ON searches FOR INSERT WITH CHECK (auth.uid() = user_id);
CREATE POLICY "searches_delete" ON searches FOR DELETE USING (auth.uid() = user_id);

CREATE POLICY "jobs_select" ON jobs FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY "jobs_insert" ON jobs FOR INSERT WITH CHECK (auth.uid() = user_id);
CREATE POLICY "jobs_update" ON jobs FOR UPDATE USING (auth.uid() = user_id);
CREATE POLICY "jobs_delete" ON jobs FOR DELETE USING (auth.uid() = user_id);
