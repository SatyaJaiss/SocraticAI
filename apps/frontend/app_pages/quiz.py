"""Quiz page — taking practice quizzes and reviewing graded evaluations."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

# Ensure repository root is on sys.path
root_dir = Path(__file__).resolve().parents[3]
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

import streamlit as st
from apps.frontend.services.api_client import SocraticAIClientError
from apps.frontend.utils.state import ensure_authenticated, get_client, set_quiz_in_state, student_id

ensure_authenticated()

st.header("Practice Quiz", icon=":material/quiz:")

quiz = st.session_state.get("active_quiz")
if quiz is None:
    st.info(
        "No active quiz. Ask the AI tutor a question with **Generate practice quiz** enabled, or enter a Quiz ID below."
    )
    with st.container(horizontal=True, vertical_alignment="bottom"):
        quiz_id = st.text_input("Load a quiz by ID", placeholder="e.g. quiz-123", key="input_quiz_id")
        load_clicked = st.button("Load quiz", icon=":material/download:")

    if load_clicked and quiz_id.strip():
        try:
            loaded_quiz = get_client().get_quiz(quiz_id.strip())
            set_quiz_in_state(loaded_quiz)
            st.rerun()
        except SocraticAIClientError as exc:
            st.error(str(exc))
else:
    topic = quiz.get("topic", "General Topic")
    difficulty = quiz.get("difficulty", "Adaptive")
    questions: list[dict] = quiz.get("questions") or []

    with st.container(border=True):
        st.subheader(f"{topic} · {difficulty}")
        st.caption(f"{len(questions)} questions — answer below and submit for grading.")

    answers: dict[str, Any] = {}

    with st.form("quiz_answers"):
        for idx, question in enumerate(questions, start=1):
            qtype = question.get("type")
            st.markdown(f"**Q{idx}.** {question.get('question')}")
            if qtype == "mcq":
                options = question.get("options") or []
                answer = st.radio(
                    f"Options for Q{idx}",
                    options,
                    key=f"quiz_q_{question.get('id', idx)}",
                    label_visibility="collapsed",
                )
                answers[question["id"]] = answer
            else:
                hint = {
                    "numerical": "Enter numeric answer",
                    "subjective": "Answer in your own words",
                }.get(qtype, "Your answer")
                answer = st.text_area(
                    hint,
                    key=f"quiz_q_{question.get('id', idx)}",
                    height=90 if qtype == "subjective" else 60,
                )
                answers[question["id"]] = answer or ""

        submitted = st.form_submit_button("Submit answers", type="primary", icon=":material/send:")

    if submitted:
        payload = [
            {"question_id": qid, "answer": ans} for qid, ans in answers.items()
        ]
        try:
            with st.spinner("Grading your quiz…"):
                result = get_client().submit_quiz(student_id(), quiz.get("id"), payload)
        except SocraticAIClientError as exc:
            st.error(str(exc))
            result = None

        if result:
            st.session_state["last_evaluation"] = result

# Render previous or current evaluation
evaluation_result = st.session_state.get("last_evaluation")
if evaluation_result:
    eval_data = evaluation_result.get("evaluation") or {}
    if eval_data:
        st.divider()
        st.subheader("Quiz Results", icon=":material/grade:")
        with st.container(border=True):
            percent = float(eval_data.get("percent", 0.0))
            score = eval_data.get("score", 0)
            max_score = eval_data.get("max_score", 0)

            col1, col2 = st.columns([1, 3], vertical_alignment="center")
            col1.metric("Final Score", f"{score} / {max_score}", f"{percent:.1f}%")
            with col2:
                st.progress(min(max(percent / 100.0, 0.0), 1.0))
                st.write(eval_data.get("feedback", ""))

            weak = eval_data.get("weak_concepts") or []
            if weak:
                st.markdown("**Areas for improvement:** " + ", ".join(weak))
            if eval_data.get("next_lesson"):
                st.markdown(f"**Suggested next lesson:** {eval_data.get('next_lesson')}")

        rec = evaluation_result.get("recommendations")
        if rec:
            with st.container(border=True):
                st.subheader("Recommended Next Step", icon=":material/lightbulb:")
                st.markdown(f"**{rec.get('next_topic', 'Review')}**")
                st.write(rec.get("rationale", ""))
                daily_plan = rec.get("daily_plan") or []
                if daily_plan:
                    st.markdown("**Suggested practice items:**")
                    for item in daily_plan:
                        st.markdown(f"- {item}")
