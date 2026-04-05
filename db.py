import auth


def get_searches(user_id: str) -> list[dict]:
    return (
        auth.get_authed_client()
        .table("searches")
        .select("*")
        .eq("user_id", user_id)
        .order("created_at")
        .execute()
        .data
    )


def create_search(user_id: str, job_title: str, location: str, sites: list[str] | None = None, country: str = "Canada") -> dict:
    return (
        auth.get_authed_client()
        .table("searches")
        .insert({
            "user_id":   user_id,
            "job_title": job_title,
            "location":  location,
            "sites":     ",".join(sites) if sites else "linkedin,indeed",
            "country":   country,
        })
        .execute()
        .data[0]
    )


def delete_search(search_id: str) -> None:
    # CASCADE in the DB deletes associated jobs automatically
    auth.get_authed_client().table("searches").delete().eq("id", search_id).execute()


def upsert_jobs(jobs: list[dict], search_id: str, user_id: str) -> None:
    if not jobs:
        return
    records = [{**j, "search_id": search_id, "user_id": user_id} for j in jobs]
    (
        auth.get_authed_client()
        .table("jobs")
        .upsert(records, on_conflict="search_id,external_id", ignore_duplicates=True)
        .execute()
    )


def get_jobs_for_search(search_id: str) -> list[dict]:
    return (
        auth.get_authed_client()
        .table("jobs")
        .select("id,title,company,location,site,job_url,description,queried_at,applied")
        .eq("search_id", search_id)
        .eq("applied", False)
        .order("queried_at", desc=True)
        .execute()
        .data
    )


def get_applied_jobs(user_id: str) -> list[dict]:
    return (
        auth.get_authed_client()
        .table("jobs")
        .select("id,title,company,location,site,job_url,queried_at")
        .eq("user_id", user_id)
        .eq("applied", True)
        .order("queried_at", desc=True)
        .execute()
        .data
    )


def get_latest_queried_at(search_id: str) -> str | None:
    rows = (
        auth.get_authed_client()
        .table("jobs")
        .select("queried_at")
        .eq("search_id", search_id)
        .order("queried_at", desc=True)
        .limit(1)
        .execute()
        .data
    )
    return rows[0]["queried_at"] if rows else None


def delete_job(job_id: str) -> None:
    auth.get_authed_client().table("jobs").delete().eq("id", job_id).execute()


def mark_applied(job_id: str) -> None:
    auth.get_authed_client().table("jobs").update({"applied": True}).eq("id", job_id).execute()
