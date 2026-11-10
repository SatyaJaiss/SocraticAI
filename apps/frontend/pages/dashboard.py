"""Dashboard page — progress tracking and learning analytics."""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from apps.frontend.services.api_client import SocraticAIClientError
from apps.frontend.utils.state import get_client, student_id


def render_dashboard() -> None:
    st.subheader("📊 Learning Dashboard")
    try:
        data = get_client().get_dashboard(student_id())
    except SocraticAIClientError as exc:
        st.error(str(exc))
        return

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Name", data.get("name", "Learner"))
    col2.metric("Level", data.get("level", "—"))
    col3.metric("Quiz attempts", data.get("total_attempts", 0))
    col4.metric("Documents", data.get("total_documents", 0))

    scores = data.get("quiz_scores") or []
    history = data.get("attempt_history") or []

    if history:
        st.markdown("### Score history")
        frame = pd.DataFrame(history)
        fig = px.line(
            frame,
            x="created_at",
            y="percent",
            markers=True,
            labels={"created_at": "Attempt", "percent": "Score %"},
        )
        st.plotly_chart(fig, use_container_width=True)
    elif scores:
        st.caption("No attempt history yet — take a quiz to start the chart.")

    left, right = st.columns(2)
    with left:
        st.markdown("### Weak concepts")
        weak = data.get("weak_concepts") or []
        if weak:
            for concept in weak:
                st.markdown(f"- ⚠️ {concept}")
        else:
            st.caption("None identified yet.")
    with right:
        st.markdown("### Topics learned")
        topics = data.get("topics_learned") or []
        if topics:
            st.write(", ".join(topics))
        else:
            st.caption("No topics recorded yet.")

    memory = data.get("recent_memory_facts") or []
    if memory:
        st.markdown("### Recent memory")
        for fact in memory[-5:]:
            st.markdown(f"- *({fact.get('type')})* {fact.get('content')}")

    rec = data.get("latest_recommendation")
    if rec:
        st.markdown("### Latest recommendation")
        st.markdown(f"**{rec.get('next_topic')}** — {rec.get('rationale', '')}")

