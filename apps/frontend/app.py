"""SocraticAI — Streamlit dashboard.

Pages
-----
* **Chat** — talk to the AI tutor (optionally produce a follow-up practice quiz).
* **Quiz** — answer the latest generated quiz and get a graded evaluation.
* **Dashboard** — progress charts, weak concepts, memory and recommendations.
* **Documents** — upload PDF/TXT/MD notes and search them during lessons (RAG).

Run with ``streamlit run apps/frontend/app.py`` from the project root.
"""

from __future__ import annotations

import streamlit as st

from apps.frontend.components.sidebar import render_sidebar
from apps.frontend.pages.chat import render_chat
from apps.frontend.pages.dashboard import render_dashboard
from apps.frontend.pages.documents import render_documents
from apps.frontend.pages.quiz import render_quiz
from apps.frontend.utils.state import init_state


def main() -> None:
    st.set_page_config(
        page_title="SocraticAI",
        page_icon="🎓",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    init_state()

    st.title("🎓 SocraticAI — AI Personal Tutor")

    page = render_sidebar()

    if page == "Chat":
        render_chat()
    elif page == "Quiz":
        render_quiz()
    elif page == "Dashboard":
        render_dashboard()
    else:
        render_documents()


if __name__ == "__main__":
    main()

