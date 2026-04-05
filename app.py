import streamlit as st
import pandas as pd

import auth
import db
from scraper import run_scrape
from h1b import flag_h1b

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
# Tab render functions
# ---------------------------------------------------------------------------

user_id = st.session_state["user_id"]


def _clean(df: pd.DataFrame) -> pd.DataFrame:
    """Clean up scraped data — fix nan companies, drop exact duplicates."""
    df = df.copy()
    df["company"] = df["company"].replace("nan", "").fillna("")
    df = df.drop_duplicates(subset=["title", "company"], keep="first")
    return df


def render_search_tab(search: dict) -> None:
    saved_sites = (search.get("sites") or "linkedin,indeed").split(",")

    # Header row
    col_title, col_li, col_in, col_btn, col_close = st.columns([4, 1, 1, 1.5, 1.2])
    with col_title:
        st.subheader(f"{search['job_title']} — {search['location']}")
    with col_li:
        use_linkedin = st.checkbox("LinkedIn", value="linkedin" in saved_sites, key=f"li_{search['id']}")
    with col_in:
        use_indeed   = st.checkbox("Indeed",   value="indeed"   in saved_sites, key=f"in_{search['id']}")
    with col_btn:
        refresh = st.button("Refresh Jobs", key=f"refresh_{search['id']}", use_container_width=True)
    with col_close:
        if st.button("✕ Delete Search", key=f"del_{search['id']}", use_container_width=True):
            db.delete_search(search["id"])
            st.session_state["nav_index"] = 0
            st.rerun()

    if refresh:
        selected = [s for s, on in [("linkedin", use_linkedin), ("indeed", use_indeed)] if on]
        if not selected:
            st.warning("Select at least one site.")
        else:
            with st.spinner("Scraping jobs — this may take 10–20 seconds..."):
                jobs = run_scrape(search["job_title"], search["location"], sites=selected)
                db.upsert_jobs(jobs, search["id"], user_id)
            st.rerun()

    rows = db.get_jobs_for_search(search["id"])
    if not rows:
        st.info("No jobs yet. Click **🔄 Refresh** to search.")
        return

    df = flag_h1b(_clean(pd.DataFrame(rows)))

    # Metrics row
    linkedin_count = len(df[df["site"] == "linkedin"])
    indeed_count   = len(df[df["site"] == "indeed"])
    h1b_count      = len(df[df["h1b_sponsor"]])
    m1, m2, m3, m4, _ = st.columns([1, 1, 1, 1, 4])
    m1.metric("Total Jobs", len(df))
    m2.metric("LinkedIn", linkedin_count)
    m3.metric("Indeed", indeed_count)
    m4.metric("H1B Sponsors", h1b_count)

    st.markdown("")

    original_applied = dict(zip(df["id"], df["applied"]))

    edited = st.data_editor(
        df[["title", "company", "h1b_sponsor", "location", "site", "job_url", "queried_at", "applied"]],
        column_config={
            "title":       st.column_config.TextColumn("Title", width="large"),
            "company":     st.column_config.TextColumn("Company", width="medium"),
            "h1b_sponsor": st.column_config.CheckboxColumn("H1B Sponsor", width="small"),
            "location":    st.column_config.TextColumn("Location", width="medium"),
            "site":        st.column_config.TextColumn("Source", width="small"),
            "job_url":     st.column_config.LinkColumn("Apply", display_text="Apply →", width="small"),
            "queried_at":  st.column_config.DatetimeColumn("Found At", format="MMM D, h:mm a", width="medium"),
            "applied":     st.column_config.CheckboxColumn("Applied?", width="small"),
        },
        disabled=["title", "company", "h1b_sponsor", "location", "site", "job_url", "queried_at"],
        hide_index=True,
        use_container_width=True,
        key=f"editor_{search['id']}",
    )

    # Persist applied changes
    changed = False
    for idx, row in edited.iterrows():
        job_id = df.loc[idx, "id"]
        if row["applied"] and not original_applied[job_id]:
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

        st.markdown("**Search on:**")
        col_li, col_in = st.columns(2)
        with col_li:
            use_linkedin = st.checkbox("LinkedIn", value=True, key="new_li")
        with col_in:
            use_indeed   = st.checkbox("Indeed",   value=True, key="new_in")

        st.markdown("")
        if st.button("Save & Search", use_container_width=True, type="primary"):
            if not job_title or not location:
                st.warning("Please enter a job title and location.")
            else:
                selected = [s for s, on in [("linkedin", use_linkedin), ("indeed", use_indeed)] if on]
                if not selected:
                    st.warning("Select at least one site.")
                else:
                    with st.spinner("Scraping jobs..."):
                        search = db.create_search(uid, job_title, location, sites=selected)
                        jobs   = run_scrape(job_title, location, sites=selected)
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
            "queried_at":  st.column_config.DatetimeColumn("Found At", format="MMM D, h:mm a", width="medium"),
        },
        hide_index=True,
        use_container_width=True,
    )


# ---------------------------------------------------------------------------
# Sidebar + main layout
# ---------------------------------------------------------------------------

searches = db.get_searches(user_id)

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
