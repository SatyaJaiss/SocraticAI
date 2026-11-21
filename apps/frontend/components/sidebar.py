"""Sidebar component for session configuration and navigation."""

from __future__ import annotations

import streamlit as st
from apps.frontend.services.api_client import SocraticAIClientError
from apps.frontend.utils.state import get_client


def render_sidebar_session_info() -> None:
    """Render session controls (Student ID, API health status) in the sidebar."""
    with st.sidebar:
        st.subheader("Session", icon=":material/account_circle:")
        st.text_input(
            "Student ID",
            value=st.session_state.get("student_id", "student-1"),
            key="student_id",
            help="Unique identifier for current student session and profile",
        )
        try:
            health = get_client().health()
            demo = health.get("demo_mode", False)
            status_text = health.get("status", "healthy")
            st.caption(
                f"API: {status_text}"
                + (" · demo mode" if demo else "")
            )
        except SocraticAIClientError:
            st.caption("API: unreachable — check backend container")


def render_sidebar() -> str:
    """Backward compatibility alias."""
    render_sidebar_session_info()
    return "Chat"
