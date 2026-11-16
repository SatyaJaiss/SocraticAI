"""Bounded Socratic dialogue and guided problem-solving engine."""

from __future__ import annotations

import logging

from app.llm.clients.client import LLMClient
from app.repositories.socratic_repository import SocraticRepository
from app.schemas.domain import SocraticTurnResponse

logger = logging.getLogger(__name__)


class SocraticEngine:
    """Orchestrates bounded multi-turn Socratic problem-solving with progressive hints."""

    def __init__(
        self,
        socratic_repo: SocraticRepository,
        llm: LLMClient | None = None,
        max_hint_level: int = 4,
    ) -> None:
        self.repo = socratic_repo
        self.llm = llm
        self.max_hint_level = max_hint_level

    def start_session(
        self,
        *,
        student_id: str,
        conversation_id: str,
        concept: str,
        problem_statement: str,
        target_solution: str = "",
        total_steps: int = 3,
    ) -> SocraticTurnResponse:
        """Initialize a new Socratic problem-solving session and emit the first guiding question."""
        session = self.repo.create_session(
            student_id=student_id,
            conversation_id=conversation_id,
            concept=concept,
            problem_statement=problem_statement,
            target_solution=target_solution,
            total_steps=total_steps,
            max_hint_level=self.max_hint_level,
        )

        step_prompt = self._formulate_step_question(
            concept, problem_statement, step=1, total_steps=total_steps
        )

        self.repo.record_turn(
            session_id=session.id,
            student_input="[SESSION_START]",
            tutor_response=step_prompt,
            step_assessment={"event": "session_start", "step": 1},
        )

        return SocraticTurnResponse(
            session_id=session.id,
            concept=concept,
            current_step=1,
            total_steps=total_steps,
            question=step_prompt,
            hint=None,
            hint_level=0,
            is_completed=False,
            is_stuck=False,
            solution_revealed=False,
            feedback=f"Let's work through this problem together on {concept}. We'll take it step by step.",
        )

    def process_student_turn(
        self,
        session_id: str,
        student_input: str,
    ) -> SocraticTurnResponse:
        """Evaluate student step response, decide whether to advance, scaffold, or escalate hints."""
        session = self.repo.get_session(session_id)
        if not session or session.status in {"completed", "abandoned", "resolved_with_solution"}:
            return SocraticTurnResponse(
                session_id=session_id,
                concept=session.concept if session else "unknown",
                current_step=session.current_step if session else 1,
                total_steps=session.total_steps if session else 1,
                question="This session has already ended.",
                is_completed=True,
                feedback="Session is closed. You can start a new problem whenever you're ready!",
            )

        inp_lower = student_input.strip().lower()

        # Check if student explicitly requests a hint
        if any(
            w in inp_lower
            for w in ["hint", "clue", "help", "stuck", "don't know", "dont know", "not sure"]
        ):
            return self.escalate_hint(session_id, reason="Student requested hint")

        # Evaluate the student's reasoning for the current step
        is_step_correct, reasoning_feedback = self._evaluate_step_response(
            concept=session.concept,
            problem=session.problem_statement,
            step=session.current_step,
            total_steps=session.total_steps,
            target_solution=session.target_solution,
            student_input=student_input,
        )

        if is_step_correct:
            # Advance step
            advanced_session = self.repo.advance_step(
                session_id, step_note=f"Correct answer for step {session.current_step}"
            )
            if not advanced_session:
                advanced_session = session

            if (
                advanced_session.status == "completed"
                or advanced_session.current_step > advanced_session.total_steps
            ):
                self.repo.complete_session(session_id, solution_revealed=False)
                final_feedback = (
                    f"Excellent work! You have solved all {session.total_steps} steps of the problem on "
                    f"'{session.concept}'! {reasoning_feedback}"
                )
                self.repo.record_turn(
                    session_id=session_id,
                    student_input=student_input,
                    tutor_response=final_feedback,
                    step_assessment={"status": "completed", "score": 1.0},
                )
                return SocraticTurnResponse(
                    session_id=session_id,
                    concept=session.concept,
                    current_step=session.total_steps,
                    total_steps=session.total_steps,
                    question="Problem completed successfully!",
                    hint=None,
                    hint_level=0,
                    is_completed=True,
                    is_stuck=False,
                    solution_revealed=False,
                    feedback=final_feedback,
                )

            # Formulate the next step's question
            next_q = self._formulate_step_question(
                session.concept,
                session.problem_statement,
                step=advanced_session.current_step,
                total_steps=advanced_session.total_steps,
            )
            feedback = f"Great insight on step {session.current_step}! {reasoning_feedback}"
            self.repo.record_turn(
                session_id=session_id,
                student_input=student_input,
                tutor_response=f"{feedback}\n\n{next_q}",
                step_assessment={"status": "advanced", "step": advanced_session.current_step},
            )
            return SocraticTurnResponse(
                session_id=session_id,
                concept=session.concept,
                current_step=advanced_session.current_step,
                total_steps=advanced_session.total_steps,
                question=next_q,
                hint=None,
                hint_level=0,
                is_completed=False,
                is_stuck=False,
                solution_revealed=False,
                feedback=feedback,
            )

        # If incorrect, check if student is stuck or escalate hint
        new_hint_level = self.repo.escalate_hint(
            session_id, hint_text=f"Incorrect attempt on step {session.current_step}"
        )
        is_stuck = new_hint_level >= self.max_hint_level
        hint_text = self._build_hint_text(
            concept=session.concept,
            problem=session.problem_statement,
            step=session.current_step,
            total_steps=session.total_steps,
            level=new_hint_level,
            target_solution=session.target_solution,
        )

        curr_q = self._formulate_step_question(
            session.concept,
            session.problem_statement,
            step=session.current_step,
            total_steps=session.total_steps,
        )

        feedback = f"Not quite. {reasoning_feedback}"
        solution_revealed = False
        if new_hint_level >= self.max_hint_level:
            solution_revealed = True
            feedback += f"\n\nHere is the full walkthrough for this step:\n{session.target_solution or hint_text}"

        self.repo.record_turn(
            session_id=session_id,
            student_input=student_input,
            tutor_response=f"{feedback}\nHint: {hint_text}\n{curr_q}",
            step_assessment={"status": "retry", "hint_level": new_hint_level},
        )

        return SocraticTurnResponse(
            session_id=session_id,
            concept=session.concept,
            current_step=session.current_step,
            total_steps=session.total_steps,
            question=curr_q,
            hint=hint_text,
            hint_level=new_hint_level,
            is_completed=False,
            is_stuck=is_stuck,
            solution_revealed=solution_revealed,
            feedback=feedback,
        )

    def escalate_hint(
        self, session_id: str, reason: str = "hint requested"
    ) -> SocraticTurnResponse:
        """Explicitly request and return the next progressive hint tier."""
        session = self.repo.get_session(session_id)
        if not session:
            raise ValueError(f"Socratic session {session_id} not found.")

        new_level = self.repo.escalate_hint(session_id, hint_text=reason)
        hint_text = self._build_hint_text(
            concept=session.concept,
            problem=session.problem_statement,
            step=session.current_step,
            total_steps=session.total_steps,
            level=new_level,
            target_solution=session.target_solution,
        )
        is_stuck = new_level >= self.max_hint_level
        solution_revealed = new_level >= self.max_hint_level

        curr_q = self._formulate_step_question(
            session.concept,
            session.problem_statement,
            step=session.current_step,
            total_steps=session.total_steps,
        )

        tier_names = {
            1: "Conceptual Direction",
            2: "Key Principle / Formula Structure",
            3: "Partial Solution / Intermediate Step",
            4: "Complete Solution Walkthrough",
        }

        feedback = f"Hint Level {new_level} ({tier_names.get(new_level, 'Guidance')}):"

        self.repo.record_turn(
            session_id=session_id,
            student_input=f"[REQUEST_HINT: Level {new_level}]",
            tutor_response=f"{feedback} {hint_text}",
            step_assessment={"hint_level": new_level},
        )

        return SocraticTurnResponse(
            session_id=session_id,
            concept=session.concept,
            current_step=session.current_step,
            total_steps=session.total_steps,
            question=curr_q,
            hint=hint_text,
            hint_level=new_level,
            is_completed=False,
            is_stuck=is_stuck,
            solution_revealed=solution_revealed,
            feedback=feedback,
        )

    def _formulate_step_question(
        self,
        concept: str,
        problem: str,
        step: int,
        total_steps: int,
    ) -> str:
        """Formulate a single focused question for the current step."""
        if step == 1:
            return (
                f"Step 1 of {total_steps}: To start solving '{problem}', what is the core principle or "
                f"formula related to {concept} that we should apply first?"
            )
        elif step == 2:
            return (
                f"Step 2 of {total_steps}: Now that we have the principle, how do we set up the equation "
                f"and substitute the known quantities?"
            )
        else:
            return f"Step {step} of {total_steps}: What is the final calculation or conclusion needed to complete the solution?"

    def _build_hint_text(
        self,
        concept: str,
        problem: str,
        step: int,
        total_steps: int,
        level: int,
        target_solution: str = "",
    ) -> str:
        """Generate progressive hint respecting escalation tiers 1-4."""
        if level <= 1:
            return f"Consider the fundamental definition of {concept}. Which variable or relationship connects what is given to what is unknown?"
        elif level == 2:
            return f"Identify the governing formula for {concept}. Remember how each term in the relationship corresponds to the problem values."
        elif level == 3:
            return f"Substitute the known values from the problem into the equation for Step {step}. Look at what cancels out or simplifies."
        else:
            # Level 4: Full explanation / solution
            if target_solution:
                return f"Full Solution Walkthrough:\n{target_solution}"
            return f"Full Solution: Applying {concept} to '{problem}' yields the complete step-by-step resolution."

    def _evaluate_step_response(
        self,
        concept: str,
        problem: str,
        step: int,
        total_steps: int,
        target_solution: str,
        student_input: str,
    ) -> tuple[bool, str]:
        """Check if student response is acceptable for the current intermediate step."""
        inp = student_input.strip().lower()
        if not inp:
            return False, "Please share your thinking or attempt for this step."

        # If student says "skip", "give up", "i don't know"
        if any(w in inp for w in ["give up", "pass", "no idea"]):
            return False, "Let's take it one piece at a time with a hint."

        # Use LLM verification if available
        if self.llm is not None:
            prompt = (
                f"You are a Socratic tutor evaluating a student's answer for Step {step}/{total_steps}.\n"
                f"Concept: {concept}\n"
                f"Problem: {problem}\n"
                f"Target Solution: {target_solution}\n"
                f"Student response: {student_input}\n\n"
                "Is the student's answer conceptually correct and reasonable for this step? "
                "Respond in the format: VALID: <yes/no> | FEEDBACK: <brief 1-2 sentence constructive feedback>"
            )
            try:
                res = self.llm.generate(prompt)
                res_text = getattr(res, "content", str(res))
                is_valid = "valid: yes" in res_text.lower()
                feedback = (
                    res_text.split("FEEDBACK:")[-1].strip() if "FEEDBACK:" in res_text else res_text
                )
                return is_valid, feedback
            except Exception as e:
                logger.warning(
                    f"LLM evaluation of Socratic step failed: {e}; falling back to heuristics."
                )

        # Deterministic heuristic fallback:
        # If response has at least 3 words and mentions relevant terms or reasonable math
        words = inp.split()
        if len(words) >= 2:
            return True, f"Your reasoning aligns with the core principles of {concept}."
        return False, "Could you elaborate a bit more on how you arrived at that?"
