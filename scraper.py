from jobspy import scrape_jobs  # package: python-jobspy
from datetime import datetime, timezone
import pandas as pd


def run_scrape(
    job_title: str,
    location: str,
    sites: list[str] | None = None,
    results_wanted: int = 20,
    hours_old: int = 72,
    country_indeed: str = "Canada",
) -> list[dict]:
    """
    Scrape jobs from the given sites via jobspy.
    Each site is scraped independently so one failure doesn't block the others.
    Returns a deduplicated list of job dicts ready for insertion into Supabase.
    Note: linkedin_fetch_description=True increases scrape time significantly.
    """
    if not sites:
        sites = ["linkedin", "indeed"]
    frames = []

    for site in sites:
        try:
            df = scrape_jobs(
                site_name=[site],
                search_term=job_title,
                location=location,
                results_wanted=results_wanted,
                hours_old=hours_old,
                country_indeed=country_indeed,
                linkedin_fetch_description=True,
            )
            if df is not None and not df.empty:
                frames.append(df)
        except Exception:
            pass  # site unavailable — continue with others

    if not frames:
        return []

    combined = pd.concat(frames, ignore_index=True)
    queried_at = datetime.now(timezone.utc).isoformat()

    def clean(val) -> str:
        s = str(val) if val is not None else ""
        return "" if s.lower() == "nan" else s

    def clean_bool(val) -> bool | None:
        if val is None:
            return None
        if isinstance(val, bool):
            return val
        try:
            if pd.isna(val):
                return None
        except Exception:
            pass
        s = str(val).lower()
        if s in ("true", "1", "yes"):
            return True
        if s in ("false", "0", "no"):
            return False
        return None

    return [
        {
            "external_id": clean(row.get("id")),
            "title":       clean(row.get("title")),
            "company":     clean(row.get("company")),
            "location":    clean(row.get("location")),
            "site":        clean(row.get("site")),
            "job_url":     clean(row.get("job_url")),
            "description": clean(row.get("description")),
            "easy_apply":  clean_bool(row.get("is_easy_apply")),
            "queried_at":  queried_at,
        }
        for _, row in combined.iterrows()
        if row.get("id") and str(row.get("id")).lower() != "nan"
    ]
