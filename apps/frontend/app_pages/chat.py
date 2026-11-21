"""Chat page — interactive conversation with the AI tutor."""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure repository root is on sys.path
root_dir = Path(__file__).resolve().parents[3]
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

import streamlit as st
from apps.frontend.services.api_client import SocraticAIClientError
from apps.frontend.utils.state import ensure_authenticated, get_client, set_quiz_in_state, student_id

ensure_authenticated()

st.header("AI Tutor", icon=":material/chat:")

# Top bar controls
with st.container(horizontal=True, vertical_alignment="center"):
    if st.button("Clear conversation", icon=":material/delete:"):
        st.session_state["chat_history"] = []
        st.rerun()
    st.toggle("Generate practice quiz after response", key="chat_with_quiz")

# Render conversation history
for entry in st.session_state.get("chat_history", []):
    role = entry.get("role", "assistant")
    with st.chat_message(role):
        st.markdown(entry.get("content", ""))

# Native chat input
if prompt := st.chat_input("Ask a question or describe what you want to learn…", submit_mode="disable"):
    # Append user message and display immediately
    st.session_state.setdefault("chat_history", []).append(
        {"role": "user", "content": prompt}
    )
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("The tutor is thinking…"):
            with_quiz = st.session_state.get("chat_with_quiz", False)
            try:
                result = get_client().chat(student_id(), prompt, with_quiz=with_quiz)
            except SocraticAIClientError as exc:
                st.error(str(exc))
                result = None

        if result:
            messages = result.get("messages") or []
            for msg in messages:
                if msg.get("role") == "assistant" and msg.get("content"):
                    st.markdown(msg["content"])
                    st.session_state["chat_history"].append(
                        {"role": "assistant", "content": msg["content"]}
                    )

            # If a quiz was produced, stage it for the Quiz page
            quiz = result.get("quiz")
            if quiz:
                set_quiz_in_state(quiz)
                st.success(
                    f"Quiz ready ({len(quiz.get('questions', []))} questions) — switch to Practice Quiz to answer it!"
                )

            st.session_state["last_result"] = result
