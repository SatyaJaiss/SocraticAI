"""Unit tests for PII protection, redaction, request-scoped placeholder mapping, and safe restoration."""

import pytest
from app.security.pii.entities import PIICategory
from app.security.pii.mapping import PIIMappingContext
from app.security.pii.service import PIIProtectionService


def test_email_and_name_redacted_before_inference():
    """Verify that email addresses and personal names are redacted with scoped placeholders."""
    service = PIIProtectionService()
    raw_input = (
        "My name is Rahul Sharma, my email is rahul@example.com. Please help me write an email."
    )

    redacted, _ctx, entities = service.redact_user_input(raw_input, student_id="student_123")

    # LLM must NEVER receive original name or email
    assert "Rahul Sharma" not in redacted
    assert "rahul@example.com" not in redacted
    assert "[PERSON_1]" in redacted
    assert "[EMAIL_1]" in redacted
    assert len(entities) == 2


def test_multiple_entities_receive_distinct_placeholders():
    """Verify that multiple entities of the same and different categories receive distinct placeholders."""
    service = PIIProtectionService()
    raw_input = (
        "Contact Alice at alice@example.com and Bob at bob@test.org. "
        "Call +1-555-0199 or 555-123-4567."
    )

    redacted, _ctx, _entities = service.redact_user_input(raw_input, student_id="student_123")

    assert "alice@example.com" not in redacted
    assert "bob@test.org" not in redacted
    assert "[EMAIL_1]" in redacted
    assert "[EMAIL_2]" in redacted
    assert "[PHONE_1]" in redacted
    assert "[PHONE_2]" in redacted


def test_phone_address_ssn_credit_card_redaction():
    """Verify sensitive physical addresses, SSNs, and financial accounts are redacted."""
    service = PIIProtectionService()
    raw_input = (
        "My SSN is 123-45-6789, credit card is 4111 2222 3333 4444, "
        "and I live at 742 Evergreen Terrace, Springfield, IL 62704."
    )

    redacted, _ctx, _entities = service.redact_user_input(raw_input, student_id="student_123")

    assert "123-45-6789" not in redacted
    assert "4111 2222 3333 4444" not in redacted
    assert "742 Evergreen Terrace" not in redacted
    assert "[GOVERNMENT_ID_1]" in redacted
    assert "[FINANCIAL_1]" in redacted
    assert "[ADDRESS_1]" in redacted


def test_final_response_restores_permitted_placeholders():
    """Verify that original values are restored in the final response."""
    service = PIIProtectionService()
    raw_input = "My name is John Doe, email is john@example.com."
    _, ctx, _ = service.redact_user_input(raw_input, student_id="student_123")

    # Simulated LLM response containing the placeholders
    model_response = "Hello [PERSON_1]! I will send an update to [EMAIL_1]."
    final_output = service.restore_response(model_response, ctx)

    assert "Hello John Doe!" in final_output
    assert "update to john@example.com" in final_output
    assert "[PERSON_1]" not in final_output
    assert "[EMAIL_1]" not in final_output


def test_unknown_placeholder_cannot_retrieve_personal_info():
    """Verify that an arbitrary, unknown placeholder injected by a model cannot retrieve data."""
    ctx = PIIMappingContext(request_id="req_1", student_id="student_1")
    ctx.register_entity(PIICategory.PERSON, "Legitimate User", 0, 15)

    # Model hallucinations or adversarial injection of unmapped placeholders
    hallucinated_response = "Hello [PERSON_99] and [EMAIL_1]!"
    restored = ctx.restore_text(hallucinated_response, strict=False)

    # Unknown placeholders must remain unexpanded
    assert "[PERSON_99]" in restored
    assert "[EMAIL_1]" in restored

    # Strict mode raises an error
    with pytest.raises(ValueError, match="Unauthorized placeholder"):
        ctx.restore_text(hallucinated_response, strict=True)


def test_placeholder_mappings_do_not_cross_requests_or_students():
    """Verify that mapping contexts are strictly isolated between requests and students."""
    service = PIIProtectionService()

    # Request 1 (Student A)
    _, ctx_a, _ = service.redact_user_input(
        "My name is Alice Cooper, email alice@secret.com",
        student_id="student_A",
        request_id="req_A",
    )

    # Request 2 (Student B)
    _, ctx_b, _ = service.redact_user_input(
        "My name is Bob Dylan, email bob@music.com",
        student_id="student_B",
        request_id="req_B",
    )

    # Context A knows Alice, Context B knows Bob
    assert ctx_a.get_value("[PERSON_1]") == "Alice Cooper"
    assert ctx_b.get_value("[PERSON_1]") == "Bob Dylan"

    # Context B attempting to restore Context A's text cannot cross boundaries
    cross_text = "Message for [PERSON_1] at [EMAIL_1]"
    restored_by_b = ctx_b.restore_text(cross_text)
    assert "Bob Dylan" in restored_by_b
    assert "Alice Cooper" not in restored_by_b


def test_pii_audit_summary_contains_no_raw_values():
    """Verify audit summaries record counts by category without exposing raw values."""
    service = PIIProtectionService()
    _, ctx, _ = service.redact_user_input(
        "My name is Jane Doe, email jane@example.com, phone 555-0199.",
        student_id="student_1",
    )
    summary = service.get_audit_summary(ctx)

    assert summary.total_entities_redacted == 3
    assert summary.counts_by_category.get("PERSON") == 1
    assert summary.counts_by_category.get("EMAIL") == 1
    assert summary.counts_by_category.get("PHONE") == 1
    # Raw personal data must not be in audit dictionary
    assert "Jane Doe" not in str(summary.model_dump())
    assert "jane@example.com" not in str(summary.model_dump())
