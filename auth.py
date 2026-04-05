from supabase import create_client, Client
import streamlit as st


def _anon_client() -> Client:
    return create_client(
        st.secrets["supabase"]["url"],
        st.secrets["supabase"]["anon_key"],
    )


def get_authed_client() -> Client:
    """
    Returns a Supabase client with the current user's JWT attached.
    Required for all DB operations so Row Level Security can evaluate auth.uid().
    """
    client = _anon_client()
    if "supabase_session" in st.session_state:
        client.auth.set_session(
            access_token=st.session_state["supabase_session"]["access_token"],
            refresh_token=st.session_state["supabase_session"]["refresh_token"],
        )
    return client


def login(email: str, password: str) -> tuple[bool, str]:
    try:
        res = _anon_client().auth.sign_in_with_password({"email": email, "password": password})
        st.session_state["supabase_session"] = {
            "access_token":  res.session.access_token,
            "refresh_token": res.session.refresh_token,
        }
        st.session_state["user_id"]    = res.user.id
        st.session_state["user_email"] = res.user.email
        return True, ""
    except Exception as e:
        return False, str(e)


def signup(email: str, password: str) -> tuple[bool, str]:
    try:
        _anon_client().auth.sign_up({"email": email, "password": password})
        return True, "Account created. You can now log in."
    except Exception as e:
        return False, str(e)


def logout() -> None:
    for key in ["supabase_session", "user_id", "user_email"]:
        st.session_state.pop(key, None)
