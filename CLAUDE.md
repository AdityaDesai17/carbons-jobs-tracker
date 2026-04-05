# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running the App

```bash
streamlit run app.py
```

Install dependencies:
```bash
pip install -r requirements.txt
```

No formal test suite exists. Manual testing is done by running the app and exercising features in the browser.

## Architecture

This is a Streamlit + Supabase job search tracker. All application logic lives in five Python modules:

- **`app.py`** — UI entry point. Renders sidebar navigation and three views: per-search job listings, new search form, and applied jobs. Calls into all other modules.
- **`auth.py`** — Supabase auth (login/signup). Stores the authenticated Supabase client and JWT in `st.session_state`.
- **`db.py`** — All database reads/writes via the authenticated Supabase client. Key functions: `create_search`, `get_searches`, `get_jobs_for_search`, `upsert_jobs`, `mark_applied`, `get_applied_jobs`.
- **`scraper.py`** — Wraps `python-jobspy` to scrape LinkedIn and/or Indeed. Called on search creation and job refresh. Returns a cleaned DataFrame.
- **`h1b.py`** — Loads `h1bsponsor.csv` at import time and exposes `flag_h1b(df)`, which adds an `h1b_sponsor` boolean column using fuzzy company name matching (rapidfuzz `token_set_ratio`).

## Database

Schema is in `schema.sql`. Two tables:
- `searches(id, user_id, job_title, location, created_at)`
- `jobs(id, search_id, user_id, external_id, title, company, location, site, job_url, queried_at, applied)`

Row Level Security (RLS) policies on both tables ensure users only see their own data. The unique constraint on `(search_id, external_id)` enables upsert-based deduplication.

## Configuration

Supabase credentials live in `.streamlit/secrets.toml` (not committed):
```toml
[supabase]
url = "..."
anon_key = "..."
```

Accessed in code via `st.secrets["supabase"]`.
