import streamlit as st
import pandas as pd
from datetime import datetime, timezone
from streamlit_autorefresh import st_autorefresh
from streamlit_javascript import st_javascript

import auth
import db
from scraper import run_scrape
from h1b import flag_h1b

AUTO_REFRESH_INTERVAL_MS = 5 * 60 * 1000   # check every 5 minutes
STALE_THRESHOLD_HOURS    = 1                # re-scrape if data is older than this

st.set_page_config(page_title="Job Tracker", layout="wide", initial_sidebar_state="expanded")


# ---------------------------------------------------------------------------
# Auth gate
# ---------------------------------------------------------------------------

if "supabase_session" not in st.session_state:
    st.markdown("""
    <style>
        .auth-wrap { max-width: 420px; margin: 60px auto 0 auto; }
    </style>
    <div class="auth-wrap">
        <h2>Job Tracker</h2>
        <p style="color:#aaa">Track your job search across LinkedIn and Indeed.</p>
        <hr style="margin: 1rem 0">
    </div>
    """, unsafe_allow_html=True)

    tab_login, tab_signup = st.tabs(["Login", "Sign Up"])

    with tab_login:
        with st.form("login_form"):
            email = st.text_input("Email")
            pw    = st.text_input("Password", type="password")
            if st.form_submit_button("Login", use_container_width=True):
                ok, msg = auth.login(email, pw)
                if ok:
                    st.rerun()
                else:
                    st.error(msg)

    with tab_signup:
        with st.form("signup_form"):
            email = st.text_input("Email")
            pw    = st.text_input("Password", type="password")
            if st.form_submit_button("Sign Up", use_container_width=True):
                ok, msg = auth.signup(email, pw)
                if ok:
                    st.success(msg)
                else:
                    st.error(msg)

    st.stop()


# ---------------------------------------------------------------------------
# Auto-refresh: rerun every 5 min; re-scrape searches older than 1 hour
# ---------------------------------------------------------------------------

# Returns an incrementing counter each time the timer fires
_refresh_count = st_autorefresh(interval=AUTO_REFRESH_INTERVAL_MS, key="autorefresh")

user_id = st.session_state["user_id"]

# Detect browser timezone — st_javascript returns 0 on first render, string on second
_tz = st_javascript("Intl.DateTimeFormat().resolvedOptions().timeZone")
if isinstance(_tz, str) and _tz:
    st.session_state["user_tz"] = _tz
user_tz = st.session_state.get("user_tz", "UTC")


def _run_auto_scrape(searches: list[dict]) -> None:
    """Scrape any searches whose data is older than STALE_THRESHOLD_HOURS."""
    stale = []
    for s in searches:
        latest = db.get_latest_queried_at(s["id"])
        if latest is None:
            continue
        last_dt = datetime.fromisoformat(latest.replace("Z", "+00:00"))
        age_hours = (datetime.now(timezone.utc) - last_dt).total_seconds() / 3600
        if age_hours >= STALE_THRESHOLD_HOURS:
            stale.append(s)

    if not stale:
        return

    with st.spinner(f"Auto-refreshing {len(stale)} search(es)..."):
        for s in stale:
            sites   = (s.get("sites") or "linkedin,indeed").split(",")
            country = s.get("country") or "Canada"
            jobs = run_scrape(s["job_title"], s["location"], sites=sites, country_indeed=country)
            db.upsert_jobs(jobs, s["id"], user_id)

    st.toast(f"Auto-refreshed {len(stale)} search(es)", icon="✅")

# ---------------------------------------------------------------------------
# Tab render functions
# ---------------------------------------------------------------------------


def _clean(df: pd.DataFrame) -> pd.DataFrame:
    """Clean up scraped data — fix nan companies, drop exact duplicates."""
    df = df.copy()
    df["company"] = df["company"].replace("nan", "").fillna("")
    df = df.drop_duplicates(subset=["title", "company"], keep="first")
    return df


ALL_SITES = ["linkedin", "indeed"]

COUNTRY_OPTIONS = ["Canada", "USA", "UK", "Australia", "India", "Germany", "Singapore", "UAE"]


def render_search_tab(search: dict) -> None:
    saved_sites = (search.get("sites") or "linkedin,indeed").split(",")
    country = search.get("country") or "Canada"

    # Header row
    col_title, col_btn, col_close = st.columns([5, 1.5, 1.2])
    with col_title:
        st.subheader(f"{search['job_title']} — {search['location']}")
    with col_btn:
        refresh = st.button("Refresh Jobs", key=f"refresh_{search['id']}", use_container_width=True)
    with col_close:
        if st.button("✕ Delete Search", key=f"del_{search['id']}", use_container_width=True):
            db.delete_search(search["id"])
            st.session_state["nav_index"] = 0
            st.rerun()

    # Site checkboxes
    site_cols = st.columns(len(ALL_SITES))
    site_checks = {}
    labels = {"zip_recruiter": "ZipRecruiter", "glassdoor": "Glassdoor",
              "google": "Google", "naukri": "Naukri", "linkedin": "LinkedIn", "indeed": "Indeed"}
    for col, site in zip(site_cols, ALL_SITES):
        with col:
            site_checks[site] = st.checkbox(
                labels.get(site, site.title()),
                value=site in saved_sites,
                key=f"{site}_{search['id']}",
            )

    if refresh:
        selected = [s for s, on in site_checks.items() if on]
        if not selected:
            st.warning("Select at least one site.")
        else:
            with st.spinner("Scraping jobs — LinkedIn descriptions add 30–60 seconds..."):
                jobs = run_scrape(search["job_title"], search["location"], sites=selected, country_indeed=country)
                db.upsert_jobs(jobs, search["id"], user_id)
            st.rerun()

    rows = db.get_jobs_for_search(search["id"])
    if not rows:
        st.info("No jobs yet. Click **Refresh Jobs** to search.")
        return

    df = flag_h1b(_clean(pd.DataFrame(rows)))

    # Metrics row
    h1b_count = len(df[df["h1b_sponsor"]])
    m1, m2, _ = st.columns([1, 1, 6])
    m1.metric("Total Jobs", len(df))
    m2.metric("H1B Sponsors", h1b_count)

    st.markdown("")

    # Filter + toggle controls
    _, fc1, _ = st.columns([0.1, 1.5, 6])
    with fc1:
        show_desc = st.toggle("Show Descriptions", key=f"desc_{search['id']}")

    display_df = df.copy()
    display_df["delete"] = False

    original_applied = dict(zip(df["id"], df["applied"]))

    base_cols = ["applied", "job_url", "title", "company", "h1b_sponsor", "location", "site", "queried_at", "delete"]
    col_config = {
        "title":       st.column_config.TextColumn("Title", width="large"),
        "company":     st.column_config.TextColumn("Company", width="medium"),
        "h1b_sponsor": st.column_config.CheckboxColumn("H1B Sponsor", width="small"),
        "location":    st.column_config.TextColumn("Location", width="medium"),
        "site":        st.column_config.TextColumn("Source", width="small"),
        "job_url":     st.column_config.LinkColumn("Apply", display_text="Apply →", width="small"),
        "queried_at":  st.column_config.DatetimeColumn("Found At", format="MMM D, h:mm a", timezone=user_tz, width="medium"),
        "applied":     st.column_config.CheckboxColumn("Applied?", width="small"),
        "delete":      st.column_config.CheckboxColumn("Delete", width="small"),
    }

    if show_desc:
        base_cols = ["applied", "job_url", "title", "company", "h1b_sponsor", "location", "site", "description", "queried_at", "delete"]
        col_config["description"] = st.column_config.TextColumn("Description", width="large")

    edited = st.data_editor(
        display_df[base_cols],
        column_config=col_config,
        disabled=["title", "company", "h1b_sponsor", "location", "site", "job_url", "description", "queried_at"],
        hide_index=True,
        use_container_width=True,
        key=f"editor_{search['id']}_{show_desc}",
    )

    display_id_map = display_df["id"].to_dict()  # {df_index: job_id}
    changed = False

    for idx, row in edited.iterrows():
        job_id = display_id_map.get(idx)
        if not job_id:
            continue
        if row.get("delete"):
            db.delete_job(job_id)
            changed = True
        elif row["applied"] and not original_applied.get(job_id):
            db.mark_applied(job_id)
            changed = True

    if changed:
        st.rerun()


def render_new_search_tab(uid: str) -> None:
    col = st.columns([1, 2, 1])[1]
    with col:
        st.subheader("New Search")
        job_title = st.text_input("Job Title", placeholder="e.g. Data Analyst")
        location  = st.text_input("Location",  placeholder="e.g. Vancouver, BC")
        country   = st.selectbox("Country (for Indeed/Glassdoor)", COUNTRY_OPTIONS, index=0, key="new_country")

        st.markdown("**Search on:**")
        site_cols = st.columns(2)
        site_checks = {}
        labels = {"linkedin": "LinkedIn", "indeed": "Indeed"}
        for i, site in enumerate(ALL_SITES):
            with site_cols[i]:
                site_checks[site] = st.checkbox(labels[site], value=True, key=f"new_{site}")

        st.markdown("")
        if st.button("Save & Search", use_container_width=True, type="primary"):
            if not job_title or not location:
                st.warning("Please enter a job title and location.")
            else:
                selected = [s for s, on in site_checks.items() if on]
                if not selected:
                    st.warning("Select at least one site.")
                else:
                    with st.spinner("Scraping jobs — LinkedIn descriptions add 30–60 seconds..."):
                        search = db.create_search(uid, job_title, location, sites=selected, country=country)
                        jobs   = run_scrape(job_title, location, sites=selected, country_indeed=country)
                        db.upsert_jobs(jobs, search["id"], uid)
                    st.rerun()


def render_applied_tab(uid: str) -> None:
    st.subheader("Applied Jobs")
    rows = db.get_applied_jobs(uid)
    if not rows:
        st.info("No applied jobs yet. Check the **Applied?** box on any job to move it here.")
        return

    df = flag_h1b(_clean(pd.DataFrame(rows)))
    st.metric("Total Applied", len(df))
    st.markdown("")

    st.dataframe(
        df[["title", "company", "h1b_sponsor", "location", "site", "job_url", "queried_at"]],
        column_config={
            "title":       st.column_config.TextColumn("Title", width="large"),
            "company":     st.column_config.TextColumn("Company", width="medium"),
            "h1b_sponsor": st.column_config.CheckboxColumn("H1B Sponsor", width="small"),
            "location":    st.column_config.TextColumn("Location", width="medium"),
            "site":        st.column_config.TextColumn("Source", width="small"),
            "job_url":     st.column_config.LinkColumn("Apply", display_text="Apply →", width="small"),
            "queried_at":  st.column_config.DatetimeColumn("Found At", format="MMM D, h:mm a", timezone=user_tz, width="medium"),
        },
        hide_index=True,
        use_container_width=True,
    )


# ---------------------------------------------------------------------------
# Sidebar + main layout
# ---------------------------------------------------------------------------

searches = db.get_searches(user_id)

# Auto-scrape stale searches only when the timer fires (not on every user interaction)
_last_seen = st.session_state.get("_last_refresh_count", -1)
if _refresh_count > 0 and _refresh_count != _last_seen:
    st.session_state["_last_refresh_count"] = _refresh_count
    _run_auto_scrape(searches)
    st.rerun()

with st.sidebar:
    st.markdown("## Job Tracker")
    st.divider()
    st.markdown(f"**{st.session_state['user_email']}**")
    if st.button("Logout", use_container_width=True):
        auth.logout()
        st.rerun()
    st.divider()

    # Navigation
    nav_options = (
        [f"{s['job_title']} — {s['location']}" for s in searches]
        + ["➕ New Search", "✅ Applied"]
    )
    # Default to first search or New Search if none
    default_idx = 0 if searches else len(searches)
    selected = st.radio(
        "My Searches",
        nav_options,
        index=st.session_state.get("nav_index", default_idx),
        label_visibility="collapsed",
    )
    st.session_state["nav_index"] = nav_options.index(selected)

# Main area
if selected == "➕ New Search":
    render_new_search_tab(user_id)
elif selected == "✅ Applied":
    render_applied_tab(user_id)
else:
    # Find the matching search
    search = next((s for s in searches if f"{s['job_title']} — {s['location']}" == selected), None)
    if search:
        render_search_tab(search)
