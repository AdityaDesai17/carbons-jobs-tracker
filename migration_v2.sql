-- Migration v2: add description, easy_apply, country columns
-- Run in Supabase Dashboard → SQL Editor → New Query

ALTER TABLE searches
  ADD COLUMN IF NOT EXISTS sites    TEXT NOT NULL DEFAULT 'linkedin,indeed',
  ADD COLUMN IF NOT EXISTS country  TEXT NOT NULL DEFAULT 'Canada';

ALTER TABLE jobs
  ADD COLUMN IF NOT EXISTS description TEXT,
  ADD COLUMN IF NOT EXISTS easy_apply  BOOLEAN;
