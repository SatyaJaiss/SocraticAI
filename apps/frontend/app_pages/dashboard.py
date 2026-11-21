"""Dashboard page — progress tracking and learning analytics."""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure repository root is on sys.path
root_dir = Path(__file__).resolve().parents[3]
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

import pandas as pd
import streamlit as st
from apps.frontend.services.api_client import SocraticAIClientError
from apps.frontend.utils.state import get_client, student_id

st.header("Learning Dashboard", icon=":material/analytics:")

try:
    data = get_client().get_dashboard(student_id())
except SocraticAIClientError as exc:
    st.error(str(exc))
    data = {}

if data:
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Name", data.get("name", "Learner"), border=True)
    col2.metric("Level", data.get("level", "—"), border=True)
    col3.metric("Quiz attempts", data.get("total_attempts", 0), border=True)
    col4.metric("Documents", data.get("total_documents", 0), border=True)

    scores = data.get("quiz_scores") or []
    history = data.get("attempt_history") or []

    if history:
        with st.container(border=True):
            st.subheader("Score History", icon=":material/trending_up:")
            frame = pd.DataFrame(history)
            if "created_at" in frame.columns and "percent" in frame.columns:
                try:
                    frame["time"] = pd.to_datetime(frame["created_at"]).dt.strftime("%m-%d %H:%M")
                    chart_data = frame.set_index("time")[["percent"]]
                    st.line_chart(chart_data, alt="Score percentage progression over quiz attempts")
                except Exception:
                    st.line_chart(frame["percent"], alt="Score percentage progression over quiz attempts")
    elif scores:
        st.caption("Take quizzes over time to view the progression chart.")

    left, right = st.columns(2)
    with left:
        with st.container(border=True):
            st.subheader("Weak Concepts", icon=":material/warning:")
            weak = data.get("weak_concepts") or []
            if weak:
                for concept in weak:
                    st.markdown(f"- ⚠️ {concept}")
            else:
                st.caption("None identified yet — great work!")

    with right:
        with st.container(border=True):
            st.subheader("Topics Learned", icon=":material/school:")
            topics = data.get("topics_learned") or []
            if topics:
                st.write(", ".join(topics))
            else:
                st.caption("No topics recorded yet.")

    memory = data.get("recent_memory_facts") or []
    if memory:
        with st.container(border=True):
            st.subheader("Recent Memory Insights", icon=":material/psychology:")
            for fact in memory[-5:]:
                st.markdown(f"- *({fact.get('type', 'fact')})* {fact.get('content')}")

    rec = data.get("latest_recommendation")
    if rec:
        with st.container(border=True):
            st.subheader("Latest Recommendation", icon=":material/lightbulb:")
            st.markdown(f"**{rec.get('next_topic', 'Review')}** — {rec.get('rationale', '')}")
