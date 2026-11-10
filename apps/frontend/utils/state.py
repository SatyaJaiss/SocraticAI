"""Streamlit session state management and client access."""

from __future__ import annotations

import streamlit as st

from apps.frontend.services.api_client import SocraticAIClient


def get_client() -> SocraticAIClient:
    """Return or initialize the session-state SocraticAIClient instance."""
    if "client" not in st.session_state:
        st.session_state.client = SocraticAIClient()
    return st.session_state.client


def student_id() -> str:
    """Return current student ID or fallback to student-1."""
    return st.session_state.get("student_id", "").strip() or "student-1"


def set_quiz_in_state(quiz: dict | None) -> None:
    """Stage a quiz into the active session state."""
    if quiz:
        st.session_state["active_quiz"] = quiz
        st.session_state["active_quiz_id"] = quiz.get("id")


def init_state() -> None:
    """Ensure baseline session state keys are present."""
    st.session_state.setdefault("student_id", "student-1")
    st.session_state.setdefault("chat_history", [])
    st.session_state.setdefault("active_quiz", None)
    st.session_state.setdefault("active_quiz_id", None)
    st.session_state.setdefault("last_evaluation", None)
