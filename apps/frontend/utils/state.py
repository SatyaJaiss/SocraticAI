"""Streamlit session state management and client access."""

from __future__ import annotations

import streamlit as st

from apps.frontend.services.api_client import SocraticAIClient, SocraticAIClientError


def get_client() -> SocraticAIClient:
    """Return or initialize the session-state SocraticAIClient instance."""
    if "client" not in st.session_state:
        st.session_state.client = SocraticAIClient()
    client: SocraticAIClient = st.session_state.client
    cached_token = st.session_state.get("auth_token")
    if cached_token and not client.token:
        client.set_token(cached_token)
    return client


def student_id() -> str:
    """Return current student ID or fallback to student-1."""
    return st.session_state.get("student_id", "").strip() or "student-1"


def set_quiz_in_state(quiz: dict | None) -> None:
    """Stage a quiz into the active session state."""
    if quiz:
        st.session_state["active_quiz"] = quiz
        st.session_state["active_quiz_id"] = quiz.get("id")


def ensure_authenticated() -> bool:
    """Ensure client has a valid Bearer token, auto-authenticating default student if needed."""
    client = get_client()
    if client.token:
        return True

    # Try session state cached token
    cached_token = st.session_state.get("auth_token")
    if cached_token:
        client.set_token(cached_token)
        return True

    # Auto-login default demo student so first-time visitors can chat immediately
    sid = student_id()
    if sid == "student-1":
        try:
            res = client.login("student-1", "password123")
            tok = res.get("access_token")
            if tok:
                client.set_token(tok)
                st.session_state["auth_token"] = tok
                st.session_state["authenticated"] = True
                st.session_state["student_name"] = res.get("student", {}).get("name", "Learner")
                return True
        except SocraticAIClientError:
            try:
                res = client.register("student-1", "password123", name="Learner")
                tok = res.get("access_token")
                if tok:
                    client.set_token(tok)
                    st.session_state["auth_token"] = tok
                    st.session_state["authenticated"] = True
                    st.session_state["student_name"] = res.get("student", {}).get("name", "Learner")
                    return True
            except Exception:
                pass
    return False


def init_state() -> None:
    """Ensure baseline session state keys are present and auto-authenticate."""
    st.session_state.setdefault("student_id", "student-1")
    st.session_state.setdefault("auth_token", None)
    st.session_state.setdefault("authenticated", False)
    st.session_state.setdefault("student_name", "Learner")
    st.session_state.setdefault("chat_history", [])
    st.session_state.setdefault("active_quiz", None)
    st.session_state.setdefault("active_quiz_id", None)
    st.session_state.setdefault("last_evaluation", None)

    ensure_authenticated()
