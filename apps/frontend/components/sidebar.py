"""Sidebar component for session configuration and authentication."""

from __future__ import annotations

import streamlit as st
from apps.frontend.services.api_client import SocraticAIClientError
from apps.frontend.utils.state import ensure_authenticated, get_client, student_id


def render_sidebar_session_info() -> None:
    """Render session controls and authentication in the sidebar."""
    with st.sidebar:
        st.subheader("Session & Auth", icon=":material/account_circle:")

        client = get_client()
        is_auth = ensure_authenticated()

        if is_auth and client.token:
            current_id = student_id()
            name = st.session_state.get("student_name", "Learner")
            st.success(f"Signed in: **{current_id}** ({name})")

            with st.expander("Switch / sign in account", expanded=False):
                _render_auth_form(client)
        else:
            st.warning("Please sign in or select account.")
            _render_auth_form(client)

        st.divider()
        try:
            health = client.health()
            demo = health.get("demo_mode", False)
            status_text = health.get("status", "healthy")
            st.caption(
                f"API: {status_text}"
                + (" · demo mode" if demo else "")
            )
        except SocraticAIClientError:
            st.caption("API: unreachable — check backend container")


def _render_auth_form(client) -> None:
    tab_signin, tab_register = st.tabs(["Sign In", "Register"])

    with tab_signin:
        with st.form("signin_form"):
            sid = st.text_input("Student ID", value=st.session_state.get("student_id", "student-1"), key="signin_sid")
            pwd = st.text_input("Password", type="password", value="password123", key="signin_pwd")
            submitted = st.form_submit_button("Sign In", type="primary", icon=":material/login:")

        if submitted:
            try:
                res = client.login(sid.strip(), pwd)
                tok = res.get("access_token")
                if tok:
                    client.set_token(tok)
                    st.session_state["auth_token"] = tok
                    st.session_state["student_id"] = sid.strip()
                    st.session_state["authenticated"] = True
                    st.session_state["student_name"] = res.get("student", {}).get("name", "Learner")
                    st.success("Signed in successfully!")
                    st.rerun()
            except SocraticAIClientError as exc:
                st.error(str(exc))

    with tab_register:
        with st.form("register_form"):
            reg_sid = st.text_input("Student ID", key="reg_sid", placeholder="e.g. alice-99")
            reg_name = st.text_input("Name", key="reg_name", value="Learner")
            reg_pwd = st.text_input("Password", type="password", key="reg_pwd")
            reg_submitted = st.form_submit_button("Create Account", icon=":material/person_add:")

        if reg_submitted and reg_sid.strip() and reg_pwd:
            try:
                res = client.register(reg_sid.strip(), reg_pwd, name=reg_name.strip() or "Learner")
                tok = res.get("access_token")
                if tok:
                    client.set_token(tok)
                    st.session_state["auth_token"] = tok
                    st.session_state["student_id"] = reg_sid.strip()
                    st.session_state["authenticated"] = True
                    st.session_state["student_name"] = res.get("student", {}).get("name", "Learner")
                    st.success("Account created and signed in!")
                    st.rerun()
            except SocraticAIClientError as exc:
                st.error(str(exc))


def render_sidebar() -> str:
    """Backward compatibility alias."""
    render_sidebar_session_info()
    return "Chat"
