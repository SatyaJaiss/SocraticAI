"""SocraticAI — Streamlit Dashboard and AI Tutoring Platform.

Pages
-----
* **AI Tutor** — interactive conversation and Socratic guided learning.
* **Practice Quiz** — answer practice quizzes and get graded evaluation.
* **Learning Dashboard** — progress charts, weak concepts, and recommendations.
* **Study Notes (RAG)** — upload notes (PDF/TXT/MD) and index for RAG.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure repository root is on sys.path
root_dir = Path(__file__).resolve().parent.parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

import streamlit as st
from apps.frontend.components.sidebar import render_sidebar_session_info
from apps.frontend.utils.state import init_state


def main() -> None:
    st.set_page_config(
        page_title="SocraticAI — AI Personal Tutor",
        page_icon="🎓",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    init_state()

    # Streamlit Navigation with app_pages per developing-with-streamlit skill
    pages = [
        st.Page(
            "app_pages/chat.py",
            title="AI Tutor",
            icon=":material/chat:",
            default=True,
            help="Interactive Socratic conversation and personalized tutoring.",
        ),
        st.Page(
            "app_pages/quiz.py",
            title="Practice Quiz",
            icon=":material/quiz:",
            help="Take adaptive quizzes and review graded feedback.",
        ),
        st.Page(
            "app_pages/dashboard.py",
            title="Learning Dashboard",
            icon=":material/analytics:",
            help="Track score history, mastery, and weak concepts.",
        ),
        st.Page(
            "app_pages/documents.py",
            title="Study Notes (RAG)",
            icon=":material/menu_book:",
            help="Manage uploaded course materials and lecture notes.",
        ),
    ]

    nav = st.navigation(pages, position="sidebar")
    render_sidebar_session_info()
    nav.run()


if __name__ == "__main__":
    main()
