"""Quiz page — taking practice quizzes and reviewing graded evaluations."""

from __future__ import annotations

from typing import Any

import streamlit as st

from apps.frontend.services.api_client import SocraticAIClientError
from apps.frontend.utils.state import get_client, set_quiz_in_state, student_id


def render_quiz() -> None:
    st.subheader("📝 Practice Quiz")

    quiz = st.session_state.get("active_quiz")
    if quiz is None:
        st.info(
            "No quiz yet. Ask the tutor to teach a topic with the **+quiz** "
            "checkbox enabled, or load a quiz id below."
        )
        quiz_id = st.text_input("Load a quiz by id")
        if st.button("Load quiz") and quiz_id.strip():
            try:
                quiz = get_client().get_quiz(quiz_id.strip())
                set_quiz_in_state(quiz)
                st.rerun()
            except SocraticAIClientError as exc:
                st.error(str(exc))
        return

    st.markdown(f"### {quiz.get('topic')}  ·  {quiz.get('difficulty')}")
    questions: list[dict] = quiz.get("questions") or []
    st.caption(f"{len(questions)} questions — answer them below, then submit for grading.")

    answers: dict[str, Any] = {}

    with st.form("quiz_answers"):
        for idx, question in enumerate(questions, start=1):
            qtype = question.get("type")
            st.markdown(f"**Q{idx}.** {question.get('question')}")
            if qtype == "mcq":
                options = question.get("options") or []
                answer = st.radio(
                    "Select one",
                    options,
                    key=f"quiz_q_{question['id']}",
                    label_visibility="collapsed",
                )
                answers[question["id"]] = answer
            else:
                hint = {
                    "numerical": "Enter a numeric answer",
                    "subjective": "Answer in your own words",
                }.get(qtype, "Your answer")
                answer = st.text_area(
                    hint, key=f"quiz_q_{question['id']}", height=90 if qtype == "subjective" else 60
                )
                answers[question["id"]] = answer or ""

        submitted = st.form_submit_button("Submit answers", type="primary")

    if submitted:
        payload = [
            {"question_id": qid, "answer": ans} for qid, ans in answers.items()
        ]
        try:
            with st.spinner("Grading…"):
                result = get_client().submit_quiz(student_id(), quiz.get("id"), payload)
        except SocraticAIClientError as exc:
            st.error(str(exc))
            return
        st.session_state["last_evaluation"] = result
        _render_evaluation(result)


def _render_evaluation(result: dict) -> None:
    evaluation = result.get("evaluation") or {}
    if not evaluation:
        st.warning("No evaluation was returned.")
        return
    percent = evaluation.get("percent", 0)
    st.markdown(f"## Result: **{percent:.1f}%**")
    st.progress(min(percent / 100.0, 1.0))
    st.markdown(f"Score: **{evaluation.get('score')}** / **{evaluation.get('max_score')}**")
    st.write(evaluation.get("feedback", ""))

    weak = evaluation.get("weak_concepts") or []
    if weak:
        st.markdown("**Weak areas:** " + ", ".join(weak))
    if evaluation.get("next_lesson"):
        st.markdown(f"**Next lesson:** {evaluation.get('next_lesson')}")

    rec = result.get("recommendations")
    if rec:
        st.markdown("### Recommended next step")
        st.markdown(f"**{rec.get('next_topic')}**")
        st.write(rec.get("rationale", ""))
        for item in rec.get("daily_plan") or []:
            st.markdown(f"- {item}")

    st.success("Evaluation saved. Open the Dashboard tab to see your progress.")

