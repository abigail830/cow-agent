from app.platform.guardrails.pii_patterns import redact_sensitive_text


def test_redact_api_key():
    text = "use sk-abcdefghijklmnopqrstuvwxyz1234567890 here"
    redacted, count = redact_sensitive_text(text)
    assert count >= 1
    assert "sk-abc" not in redacted
    assert "[REDACTED_API_KEY]" in redacted


def test_redact_password_assignment():
    text = "password=SuperSecret123"
    redacted, count = redact_sensitive_text(text)
    assert count >= 1
    assert "SuperSecret123" not in redacted


def test_redact_no_change_for_normal_text():
    text = "Show me inventory for warehouse A"
    redacted, count = redact_sensitive_text(text)
    assert count == 0
    assert redacted == text
