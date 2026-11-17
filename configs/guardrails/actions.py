"""Custom actions for NeMo Guardrails."""

from nemoguardrails.actions import action


@action(name="check_jailbreak")
async def check_jailbreak(context: dict | None = None) -> bool:
    """Action checking for prompt injection or jailbreak indicators."""
    text = (context or {}).get("user_message", "")
    injection_signatures = [
        "ignore all previous instructions",
        "system prompt override",
        "you are now DAN",
        "jailbreak",
        "disregard prior rules",
        "developer mode enabled",
    ]
    return any(sig in text.lower() for sig in injection_signatures)


@action(name="check_tool_authorization")
async def check_tool_authorization(
    tool_name: str,
    student_id: str,
    target_student_id: str | None = None,
) -> bool:
    """Validate tool authorization and enforce student-level data isolation."""
    allowed_tools = {
        "retrieve_documents",
        "get_concept_mastery",
        "record_evidence",
        "generate_quiz",
        "get_recommendations",
    }
    if tool_name not in allowed_tools:
        return False
    if target_student_id and target_student_id != student_id:
        return False
    return True
