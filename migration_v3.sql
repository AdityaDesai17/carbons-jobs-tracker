-- Migration v3: soft delete support
-- Run in Supabase Dashboard → SQL Editor → New Query

ALTER TABLE jobs ADD COLUMN IF NOT EXISTS deleted BOOLEAN NOT NULL DEFAULT FALSE;
