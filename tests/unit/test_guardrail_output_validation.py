"""Unit and penetration tests for customer output safety guardrails (P7-3).

Verifies US-020 (AC-066, AC-067) and CLAUDE.md sections 7.1, 7.3, 9:
- validate_customer_output validates AI-drafted replies before customer delivery.
- Blocks internal URLs, loopback IPs, RFC 1918 addresses, and internal VPC domains (AC-066).
- Blocks API credentials, secret tokens, passwords, and credit card numbers (AC-066).
- Blocks leakage of foreign customer IDs, UUIDs, or third-party customer emails (AC-066).
- Permits approved public URLs, company contact emails, and current customer details (AC-067).
- Supports 2-tuple unpacking (is_valid, reason) and boolean coercion.
- Integrates with assess_risk to elevate ticket risk to 'high' upon validation failure.
- Robust performance and ReDoS immunity for oversized text payloads (CWE-400).
"""

from __future__ import annotations

import time

import pytest

from agents.rules import assess_risk
from backend.app.core.guardrails import (
    validate_customer_output,
)

# ===========================================================================
# 1. Valid Customer Output Tests (AC-067)
# ===========================================================================


def test_validate_customer_output_clean_response():
    """Verify clean, helpful customer response with public docs passes validation (AC-067)."""
    draft = (
        "Hello! Thank you for contacting CloudDesk Support. "
        "To update your workspace member permissions, please visit https://app.clouddesk.com/settings/members. "
        "If you have further questions, feel free to reply directly to this email or contact support@clouddesk.com."
    )
    result = validate_customer_output(draft, current_customer_id="cust-101-acme")
    assert result.is_valid is True
    assert result.failure_reason == ""
    assert len(result.violations) == 0
    assert bool(result) is True


def test_validate_customer_output_tuple_unpacking():
    """Verify validate_customer_output supports 2-tuple unpacking (is_valid, reason)."""
    draft = "Your ticket has been marked as resolved. Have a great day!"
    is_valid, reason = validate_customer_output(
        draft, current_customer_id="cust-101-acme"
    )
    assert is_valid is True
    assert reason == ""


def test_validate_customer_output_own_customer_data_permitted():
    """Verify customer draft can reference customer's own ID and email address."""
    draft = (
        "Hello, your account cust-101-acme is currently on the enterprise tier. "
        "We sent a verification code to support@acme.test."
    )
    result = validate_customer_output(
        draft,
        current_customer_id="cust-101-acme",
        current_customer_email="support@acme.test",
    )
    assert result.is_valid is True
    assert result.failure_reason == ""


def test_validate_customer_output_empty_or_none():
    """Verify empty or None draft handling."""
    res_empty = validate_customer_output("", current_customer_id="cust-101-acme")
    assert res_empty.is_valid is True

    res_none = validate_customer_output(None, current_customer_id="cust-101-acme")
    assert res_none.is_valid is True


# ===========================================================================
# 2. Internal URL and IP Boundary Tests (AC-066, CWE-200)
# ===========================================================================


@pytest.mark.parametrize(
    "internal_url,label",
    [
        ("http://localhost:8000/api/internal", "localhost"),
        ("https://127.0.0.1:5432/admin", "127.0.0.1 loopback"),
        ("http://127.0.0.5:8080", "127.x loopback"),
        ("http://10.0.1.25:9000/metrics", "RFC 1918 10.x"),
        ("http://192.168.1.150/api", "RFC 1918 192.168.x"),
        ("http://172.16.4.10:3000", "RFC 1918 172.16.x"),
        ("http://169.254.169.254/latest/meta-data/", "AWS metadata IP"),
        ("http://service.internal/health", ".internal domain"),
        ("https://vault.corp.local/keys", ".local domain"),
        ("postgres://postgres.vpc.internal:5432/db", "vpc.internal"),
        ("redis://cache.cluster.local:6379", "cluster.local"),
        ("http://0.0.0.0:8000", "0.0.0.0 all-interfaces"),
    ],
)
def test_validate_customer_output_blocks_internal_urls(internal_url: str, label: str):
    """Verify AC-066: All internal URLs, private IPs, and internal domains are blocked."""
    draft = f"Please check the service status at {internal_url} to confirm resolution."
    result = validate_customer_output(draft, current_customer_id="cust-101-acme")
    assert result.is_valid is False, (
        f"Failed to block internal URL ({label}): {internal_url}"
    )
    assert (
        "internal url" in result.failure_reason.lower()
        or "network" in result.failure_reason.lower()
    )
    assert bool(result) is False


# ===========================================================================
# 3. Secret and Credential Leakage Tests (AC-066, CWE-798, CWE-200)
# ===========================================================================


@pytest.mark.parametrize(
    "secret,description",
    [
        ("sk-proj-abc123def456ghi789jkl012mno345pqr678", "OpenAI project key"),
        ("sk-ant-api03-abcdef1234567890abcdef1234567890", "Anthropic key"),
        ("sk-1234567890abcdef1234567890abcdef", "Legacy OpenAI key"),
        ("ghp_1234567890abcdefghijklmnopqrstuvwxyz", "GitHub personal token"),
        ("AKIAIOSFODNN7EXAMPLE", "AWS Access Key ID"),
        (
            "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.abc",
            "Bearer JWT token",
        ),
        ("password: SuperSecretP@ssw0rd!123", "Plaintext password label"),
        (
            "postgresql://postgres:dbpassword123@db.prod.internal:5432/clouddesk",
            "DB connection string with password",
        ),
        ("api_key = abcdef1234567890abcdef1234567890", "Generic API key assignment"),
        ("4532 0150 1234 5671", "Credit Card Visa PAN"),
    ],
)
def test_validate_customer_output_blocks_secrets(secret: str, description: str):
    """Verify AC-066: Secret keys, bearer tokens, passwords, and credit cards are blocked."""
    draft = f"Here is the credential you requested: {secret}. Keep it safe!"
    result = validate_customer_output(draft, current_customer_id="cust-101-acme")
    assert result.is_valid is False, f"Failed to block secret pattern ({description})"
    assert any(
        "secret" in v.lower() or "credential" in v.lower() or "card" in v.lower()
        for v in result.violations
    )
    assert bool(result) is False


# ===========================================================================
# 4. Foreign Customer Data Leakage Tests (AC-066, CWE-200)
# ===========================================================================


def test_validate_customer_output_blocks_other_customer_id():
    """Verify draft cannot leak another customer's account identifier."""
    draft = "We reviewed ticket CD-1002 from customer cust-102-globex and found a similar issue."
    result = validate_customer_output(draft, current_customer_id="cust-101-acme")
    assert result.is_valid is False
    assert any(
        "foreign customer" in v.lower() or "cust-102-globex" in v.lower()
        for v in result.violations
    )
    assert "cust-102-globex" in result.failure_reason


def test_validate_customer_output_blocks_other_customer_email():
    """Verify draft cannot leak another customer's contact email."""
    draft = "Please contact admin@globex.test for workspace permissions."
    result = validate_customer_output(
        draft,
        current_customer_id="cust-101-acme",
        current_customer_email="support@acme.test",
    )
    assert result.is_valid is False
    assert any(
        "foreign customer email" in v.lower() or "admin@globex.test" in v.lower()
        for v in result.violations
    )


def test_validate_customer_output_blocks_foreign_customer_uuid():
    """Verify draft cannot leak unassociated customer UUIDs."""
    foreign_uuid = "e7b01984-d113-4602-9852-9f35c5c64c23"
    draft = f"Your internal subscription record is linked to entity {foreign_uuid}."
    result = validate_customer_output(
        draft,
        current_customer_id="cust-101-acme",
    )
    assert result.is_valid is False
    assert any(foreign_uuid in v for v in result.violations)


def test_validate_customer_output_permits_clouddesk_support_emails():
    """Verify standard CloudDesk corporate and support emails are never flagged as foreign leaks."""
    draft = (
        "You can reach our billing desk at billing@clouddesk.demo, "
        "our security team at security@clouddesk.com, or general support at support@clouddesk.io."
    )
    result = validate_customer_output(draft, current_customer_id="cust-101-acme")
    assert result.is_valid is True
    assert result.failure_reason == ""


# ===========================================================================
# 5. Risk Assessment Integration (AC-066, CLAUDE.md 7.3)
# ===========================================================================


def test_assess_risk_elevated_by_output_validation_failure():
    """Verify AC-066: Failed customer output validation elevates workflow risk to high."""
    plan = {"actions": [{"tool": "update_ticket", "args": {"ticket_id": "CD-1001"}}]}

    # Normal clean run evaluates to low
    assert assess_risk(plan=plan, output_validation_failed=False) == "low"

    # Validation failure triggers mandatory high risk
    assert assess_risk(plan=plan, output_validation_failed=True) == "high"


# ===========================================================================
# 6. Security Penetration & Performance Tests (CWE-400 ReDoS)
# ===========================================================================


def test_security_cwe_400_redos_and_oversized_payload_protection():
    """Penetration test: Massive or adversarial strings do not cause ReDoS (CWE-400)."""
    # 50,000 characters of repetitive text mimicking markdown reply
    oversized_draft = (
        "Please visit our website at https://app.clouddesk.com/dashboard. " * 850
    )
    assert len(oversized_draft) > 50000

    start_time = time.perf_counter()
    result = validate_customer_output(
        oversized_draft, current_customer_id="cust-101-acme"
    )
    elapsed = time.perf_counter() - start_time

    assert elapsed < 0.20, (
        f"ReDoS detected in validate_customer_output: took {elapsed:.4f}s"
    )
    assert result.is_valid is True


def test_security_cwe_200_multiple_violations_reported():
    """Penetration test: Compound leak with internal IP, secret, and foreign customer id."""
    compound_leak = (
        "Internal DB at http://10.0.1.5:5432 leaked secret sk-proj-1234567890abcdef1234567890 "
        "belonging to cust-104-umbrella."
    )
    result = validate_customer_output(
        compound_leak, current_customer_id="cust-101-acme"
    )
    assert result.is_valid is False
    assert len(result.violations) >= 3
    # Check that all distinct categories are reported
    violations_text = " ".join(result.violations).lower()
    assert "internal url" in violations_text
    assert "secret" in violations_text
    assert "cust-104-umbrella" in violations_text
