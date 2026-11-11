"""Intent taxonomy and decision contracts for SocraticAI routing."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class IntentType(StrEnum):
    """The 10 closed intent classes for conversational tutoring and routing."""

    GREETING = "greeting"
    SMALL_TALK = "small_talk"
    TUTORING = "tutoring"
    QUIZ = "quiz"
    ASSESSMENT = "assessment"
    DOCUMENT_QUESTION = "document_question"
    MEMORY_QUERY = "memory_query"
    LEARNING_PROGRESS = "learning_progress"
    OFF_TOPIC = "off_topic"
    UNCLEAR = "unclear"


INTENT_CRITERIA: dict[str, str] = {
    IntentType.GREETING.value: (
        "User is greeting the assistant (e.g., 'hello', 'hi', 'good morning', 'hey there') "
        "without asking a substantive educational question."
    ),
    IntentType.SMALL_TALK.value: (
        "User is engaging in casual pleasantries, compliments, gratitude, or conversational banter "
        "(e.g., 'thank you', 'how are you doing?', 'you are awesome', 'goodbye', 'see you later')."
    ),
    IntentType.TUTORING.value: (
        "User requests a pedagogical explanation, lesson, concept walkthrough, or deep educational guidance "
        "(e.g., 'teach me photosynthesis', 'explain how quicksort works', 'can you walk me through Ohm\\'s law?')."
    ),
    IntentType.QUIZ.value: (
        "User requests a practice quiz, test questions, or problem drills to test their knowledge "
        "(e.g., 'give me a quiz on calculus', 'test my knowledge of World War 2', 'practice questions on algebra')."
    ),
    IntentType.ASSESSMENT.value: (
        "User is submitting answers to an existing test/quiz or requesting formal evaluation of their work "
        "(e.g., 'here are my answers: 1A, 2C', 'grade my solution', 'evaluate my essay on Hamlet')."
    ),
    IntentType.DOCUMENT_QUESTION.value: (
        "User asks a direct question specifically referencing uploaded course materials, documents, slides, or notes "
        "(e.g., 'what does my lecture note say about cellular respiration?', 'according to the uploaded PDF, what is the deadline?')."
    ),
    IntentType.MEMORY_QUERY.value: (
        "User asks what the assistant remembers about them, their past conversations, or prior sessions "
        "(e.g., 'what did we discuss yesterday?', 'do you remember my weak topics?', 'what was the last thing you taught me?')."
    ),
    IntentType.LEARNING_PROGRESS.value: (
        "User asks about their overall learning analytics, mastery scores, progress, or performance stats "
        "(e.g., 'how am I doing overall?', 'show my mastery level', 'what are my scores in math?')."
    ),
    IntentType.OFF_TOPIC.value: (
        "User asks about unrelated topics that fall completely outside academic tutoring "
        "(e.g., 'who won the soccer match?', 'tell me a recipe for chocolate cake', 'what is the stock price of Apple?')."
    ),
    IntentType.UNCLEAR.value: (
        "User input is ambiguous, incomplete, gibberish, or lacks enough context to determine intent "
        "(e.g., 'asdfgh', '?', 'ummm', 'wait what', 'it depends')."
    ),
}


class RoutingDecision(BaseModel):
    """The structured result of an intent routing classification."""

    intent: IntentType
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str = ""
    probabilities: dict[str, float] = Field(default_factory=dict)
    requires_clarification: bool = False
    is_greeting: bool = False
    source: str = "jev"
    metadata: dict[str, Any] = Field(default_factory=dict)
