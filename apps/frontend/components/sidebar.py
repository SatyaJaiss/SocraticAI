"""Sidebar component for session configuration and navigation."""

from __future__ import annotations

import streamlit as st

from apps.frontend.services.api_client import SocraticAIClientError
from apps.frontend.utils.state import get_client


def render_sidebar() -> str:
    """Render the sidebar controls and return the selected page name."""
    with st.sidebar:
        st.header("Session")
        st.text_input(
            "Student ID",
            value=st.session_state.get("student_id", "student-1"),
            key="student_id",
        )
        try:
            health = get_client().health()
            demo = health.get("demo_mode", False)
            st.caption(
                f"API: {health.get('status', 'unknown')}"
                + (" · demo mode" if demo else "")
            )
        except SocraticAIClientError:
            st.caption("API: unreachable — is the backend running?")

        st.divider()
        page = st.radio(
            "Navigate",
            ["Chat", "Quiz", "Dashboard", "Documents"],
        )
    return page

