"""Unit and penetration tests for secret scrubbing guardrail (P7-4).

Verifies US-022 (AC-070, AC-071), N7, and CLAUDE.md sections 7.5, 9, 13:
- scrub() redacts credit card PANs (Visa, Mastercard, Amex) using Luhn validation (AC-070).
- scrub() redacts API keys (OpenAI sk-proj-*, sk-ant-*, GitHub ghp_*, AWS AKIA*) (AC-070).
- scrub() redacts plaintext passwords, bearer tokens, and DB connection credentials (AC-070).
- Replaces all sensitive matches with ***REDACTED*** (AC-070).
- Validates that raw unparsed conversation/email bodies are rejected from customer_memory (AC-071).
- Protects against ReDoS and catastrophic backtracking with oversized inputs (CWE-400).
"""

from __future__ import annotations

import time

import pytest

from backend.app.core.guardrails import (
    REDACTION_MARKER,
    SECRET_PATTERNS,
    is_raw_ticket_body,
    scrub,
    scrub_text,
    validate_memory_content,
)

# ===========================================================================
# 1. Payment Card Scrubbing Tests (AC-070, CWE-359)
# ===========================================================================


@pytest.mark.parametrize(
    "card_number,label",
    [
        ("4532 0150 1234 5671", "Visa spaced"),
        ("4532-0150-1234-5671", "Visa dashed"),
        ("4532015012345671", "Visa contiguous"),
        ("5425 2334 3010 9903", "Mastercard spaced"),
        ("378282246310005", "Amex 15-digit contiguous"),
    ],
)
def test_scrub_redacts_luhn_valid_credit_cards(card_number: str, label: str):
    """Verify AC-070: Valid payment card numbers are replaced with ***REDACTED***."""
    note = f"Customer provided payment method {card_number} for manual invoice reconciliation."
    scrubbed = scrub(note)
    assert card_number not in scrubbed, (
        f"Failed to redact credit card ({label}): {card_number}"
    )
    assert REDACTION_MARKER in scrubbed
    assert (
        f"Customer provided payment method {REDACTION_MARKER} for manual invoice reconciliation."
        == scrubbed
    )


def test_scrub_preserves_non_card_numbers():
    """Verify non-card numeric sequences (failing Luhn test or non-card length) are not redacted."""
    note = "Server port 8080 and ticket ID 9876543210123456 with build 1740928374."
    scrubbed = scrub(note)
    assert "8080" in scrubbed
    assert "build 1740928374" in scrubbed


# ===========================================================================
# 2. API Key and Token Scrubbing Tests (AC-070, CWE-798)
# ===========================================================================


@pytest.mark.parametrize(
    "key,label",
    [
        ("sk-proj-abc123def456ghi789jkl012mno345pqr678", "OpenAI project key"),
        ("sk-ant-api03-abcdef1234567890abcdef1234567890", "Anthropic API key"),
        ("sk-1234567890abcdef1234567890abcdef", "Legacy OpenAI key"),
        ("ghp_1234567890abcdefghijklmnopqrstuvwxyz", "GitHub PAT"),
        (
            "github_pat_11AABCDEF0123456789_abcdefghijklmnopqrstuvwxyz0123456789",
            "GitHub fine-grained PAT",
        ),
        ("AKIAIOSFODNN7EXAMPLE", "AWS Access Key ID"),
    ],
)
def test_scrub_redacts_api_keys(key: str, label: str):
    """Verify AC-070: AI keys, GitHub tokens, and AWS access keys are scrubbed."""
    note = f"Customer webhook environment configured with token {key} on production."
    scrubbed = scrub(note)
    assert key not in scrubbed, f"Failed to redact API key ({label})"
    assert REDACTION_MARKER in scrubbed
    assert (
        f"Customer webhook environment configured with token {REDACTION_MARKER} on production."
        == scrubbed
    )


# ===========================================================================
# 3. Password and Credential Scrubbing Tests (AC-070, CWE-200)
# ===========================================================================


def test_scrub_redacts_plaintext_passwords():
    """Verify AC-070: Plaintext password labels and assignments are scrubbed."""
    note_colon = (
        "Temporary admin password: SuperSecretP@ssw0rd!123 - please change immediately."
    )
    scrubbed_colon = scrub(note_colon)
    assert "SuperSecretP@ssw0rd!123" not in scrubbed_colon
    assert f"password: {REDACTION_MARKER}" in scrubbed_colon

    note_equals = "Default root account password=AnotherSecret999! generated."
    scrubbed_equals = scrub(note_equals)
    assert "AnotherSecret999!" not in scrubbed_equals
    assert f"password={REDACTION_MARKER}" in scrubbed_equals


def test_scrub_redacts_database_connection_urls():
    """Verify AC-070: DB connection strings with credentials have passwords redacted."""
    note = "Customer connected to postgresql://dbuser:super_secret_db_pass@db.internal:5432/clouddesk."
    scrubbed = scrub(note)
    assert "super_secret_db_pass" not in scrubbed
    assert (
        f"postgresql://dbuser:{REDACTION_MARKER}@db.internal:5432/clouddesk" in scrubbed
    )


def test_scrub_redacts_bearer_and_jwt_tokens():
    """Verify AC-070: Bearer tokens and raw JWT strings are scrubbed."""
    jwt_token = (
        "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
        "eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIn0."
        "G5q-S9vFvQy7GfZvKx7_eXk8N2M"
    )
    note = f"Authorization header was set to Bearer {jwt_token}."
    scrubbed = scrub(note)
    assert jwt_token not in scrubbed
    assert f"Bearer {REDACTION_MARKER}" in scrubbed


# ===========================================================================
# 4. Compound Scrubbing & Structured Result Tests
# ===========================================================================


def test_scrub_compound_secrets():
    """Verify multiple distinct secrets in a single note are all scrubbed."""
    multi_secret_note = (
        "Diagnostics: Customer apiKey: sk-proj-1234567890abcdef1234567890 "
        "and card 4532 0150 1234 5671 with password: MySecretPassword!123."
    )
    scrubbed = scrub(multi_secret_note)
    assert "sk-proj-1234567890abcdef1234567890" not in scrubbed
    assert "4532 0150 1234 5671" not in scrubbed
    assert "MySecretPassword!123" not in scrubbed
    assert scrubbed.count(REDACTION_MARKER) >= 3


def test_scrub_text_structured_result():
    """Verify scrub_text provides detailed metadata on redacted tokens."""
    note = "Key: sk-proj-1234567890abcdef1234567890 on account."
    result = scrub_text(note)
    assert result.scrubbed_text == f"Key: {REDACTION_MARKER} on account."
    assert result.redacted_count >= 1
    assert "ai_api_key" in result.detected_secret_types


def test_scrub_empty_and_none():
    """Verify scrub safely handles None, empty string, and whitespace."""
    assert scrub(None) == ""
    assert scrub("") == ""
    assert scrub("   ") == "   "


def test_scrub_preserves_harmless_text():
    """Verify standard troubleshooting note is untouched when free of secrets."""
    benign = "Customer resolved issue by clearing browser cache and re-authenticating."
    assert scrub(benign) == benign


# ===========================================================================
# 5. Raw Ticket Body vs Structured Note Validation (AC-071)
# ===========================================================================


def test_is_raw_ticket_body_detects_unparsed_email_and_conversation():
    """Verify AC-071: Raw email headers or conversational ticket dumps are flagged."""
    raw_email = (
        "From: customer@example.com\n"
        "To: support@clouddesk.com\n"
        "Subject: Urgent: Unable to login\n"
        "Date: Fri, 07 Nov 2026 09:12:00 +0000\n\n"
        "Hi team,\nI have tried logging in three times and my authenticator fails."
    )
    assert is_raw_ticket_body(raw_email) is True
    assert validate_memory_content(raw_email) is False

    raw_chat = (
        "Customer: Hey, I need help with my workspace\n"
        "Agent: Sure, what is your account ID?\n"
        "Customer: cust-101-acme"
    )
    assert is_raw_ticket_body(raw_chat) is True
    assert validate_memory_content(raw_chat) is False


def test_validate_memory_content_approves_structured_notes():
    """Verify AC-071: Structured diagnosis, troubleshooting steps, and resolution notes pass."""
    structured_note = (
        "Root Cause: MFA token drift caused login lockout after 5 attempts.\n"
        "Resolution Steps: Customer generated backup codes from admin panel and reset TOTP."
    )
    assert is_raw_ticket_body(structured_note) is False
    assert validate_memory_content(structured_note) is True


# ===========================================================================
# 6. Performance & Security Penetration Tests (CWE-400 ReDoS, CWE-200)
# ===========================================================================


def test_security_cwe_400_redos_and_oversized_payload_protection():
    """Penetration test: Massive or adversarial strings do not cause ReDoS (CWE-400)."""
    # 50,000 characters of text with repetitive credential-like patterns
    adversarial_text = "password=test sk-proj-1234567890abcdef1234567890 " * 1100
    assert len(adversarial_text) > 50000

    start_time = time.perf_counter()
    scrubbed = scrub(adversarial_text)
    elapsed = time.perf_counter() - start_time

    assert elapsed < 0.20, (
        f"ReDoS vulnerability detected in scrub(): took {elapsed:.4f}s"
    )
    assert "sk-proj-1234567890abcdef1234567890" not in scrubbed
    assert REDACTION_MARKER in scrubbed


def test_secret_patterns_list_non_empty():
    """Verify SECRET_PATTERNS dictionary/list is populated and exposed."""
    assert len(SECRET_PATTERNS) >= 5
    pattern_names = [p[0] for p in SECRET_PATTERNS]
    assert "ai_api_key" in pattern_names
    assert "plaintext_password" in pattern_names
