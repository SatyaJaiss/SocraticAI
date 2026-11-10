"""Chat page — interactive conversation with the AI tutor."""

from __future__ import annotations

import streamlit as st

from apps.frontend.services.api_client import SocraticAIClientError
from apps.frontend.utils.state import get_client, set_quiz_in_state, student_id


def render_chat() -> None:
    st.subheader("💬 AI Tutor")

    if st.button("Clear conversation", use_container_width=False):
        st.session_state["chat_history"] = []
        st.rerun()

    for entry in st.session_state["chat_history"]:
        if entry["role"] == "user":
            with st.chat_message("user"):
                st.write(entry["content"])
        else:
            with st.chat_message("assistant"):
                st.markdown(entry["content"])

    with st.form("chat_form", clear_on_submit=True):
        cols = st.columns([6, 1])
        message = cols[0].text_input(
            "Your message", label_visibility="collapsed", placeholder="Teach me about fractions…"
        )
        with_quiz = cols[1].checkbox("+quiz")
        submitted = st.form_submit_button("Send")

    if submitted and message.strip():
        _send_chat_message(message.strip(), with_quiz)


def _send_chat_message(message: str, with_quiz: bool) -> None:
    st.session_state["chat_history"].append(
        {"role": "user", "content": message}
    )
    try:
        with st.spinner("The tutor is thinking…"):
            result = get_client().chat(student_id(), message, with_quiz=with_quiz)
    except SocraticAIClientError as exc:
        st.error(str(exc))
        return

    # Append all assistant messages from the graph in order.
    for msg in result.get("messages") or []:
        if msg.get("role") == "assistant" and msg.get("content"):
            st.session_state["chat_history"].append(
                {"role": "assistant", "content": msg["content"]}
            )

    # If a quiz was produced, stage it for the Quiz page.
    quiz = result.get("quiz")
    if quiz:
        set_quiz_in_state(quiz)
        st.success(f"Quiz ready ({len(quiz.get('questions', []))} questions) — open the Quiz tab to answer it.")

    st.session_state.setdefault("last_result", result)
    st.rerun()

