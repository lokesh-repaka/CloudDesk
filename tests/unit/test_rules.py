"""Unit tests for Deterministic Escalation, Severity, and Policy Rules (P7-1).

Verifies:
- ESCALATION_RULES definition, structure, and designated team mapping.
- Deterministic policy routing for core cases (CD-1005 Security, CD-1006 Data Loss,
  CD-1009 GDPR/Deletion, CD-1011 Payment Dispute, Enterprise Outage).
- Rules override model judgment unconditionally (policy rules always win).
- Severity floor calculation: rules can raise model severity, never lower it.
- Feature requests bound to low severity by policy.
- Category heuristic rule detection across 10 domain categories.
- Risk assessment (assess_risk) gating approval-required actions and policy escalations.
- Distrust vague model escalations when severity is high but confidence is low (AC-045).
- Security audit: CWE-862 (policy bypass prevention) and CWE-400 (ReDoS protection).
"""

from agents.rules import (
    ESCALATION_RULES,
    EscalationRule,
    assess_risk,
    evaluate_escalation_decision,
    matching_escalation_rules,
    rule_category,
    rule_severity,
)
from backend.app.schemas.common import CategoryEnum, SeverityEnum

# ---------------------------------------------------------------------------
# Escalation Rules Registry & Structure Tests
# ---------------------------------------------------------------------------

def test_escalation_rules_exist_and_structured():
    """ESCALATION_RULES contains defined policy rules with target teams and reasons."""
    assert isinstance(ESCALATION_RULES, list)
    assert len(ESCALATION_RULES) >= 5

    rule_ids = {r.id for r in ESCALATION_RULES}
    assert "RULE_SECURITY" in rule_ids
    assert "RULE_DATA_LOSS" in rule_ids
    assert "RULE_GDPR_DELETION" in rule_ids
    assert "RULE_PAYMENT_DISPUTE" in rule_ids
    assert "RULE_ENTERPRISE_OUTAGE" in rule_ids

    for rule in ESCALATION_RULES:
        assert isinstance(rule, EscalationRule)
        assert rule.id
        assert rule.name
        assert rule.target_team in ("Security", "Engineering", "Legal", "Billing")
        assert len(rule.policy_reason) > 10


# ---------------------------------------------------------------------------
# Deterministic Escalation Matching Tests
# ---------------------------------------------------------------------------

def test_matching_escalation_rules_security_incident_cd_1005():
    """CD-1005 scenario: Security incident escalates deterministically to Security."""
    text = "We detected unauthorized access to our account from an unrecognized IP and credentials leaked."
    matches = matching_escalation_rules(text=text, category=CategoryEnum.SECURITY)
    assert len(matches) >= 1
    assert any(m.id == "RULE_SECURITY" and m.target_team == "Security" for m in matches)


def test_matching_escalation_rules_data_loss_cd_1006():
    """CD-1006 scenario: Data loss incident escalates deterministically to Engineering."""
    text = "All project files were permanently lost after the sync error, data corrupted."
    matches = matching_escalation_rules(text=text)
    assert len(matches) >= 1
    assert any(m.id == "RULE_DATA_LOSS" and m.target_team == "Engineering" for m in matches)


def test_matching_escalation_rules_gdpr_deletion_cd_1009():
    """CD-1009 scenario: GDPR account deletion request escalates deterministically to Legal."""
    text = "I request permanent erasure of my personal data under GDPR right to be forgotten."
    matches = matching_escalation_rules(text=text)
    assert len(matches) >= 1
    assert any(m.id == "RULE_GDPR_DELETION" and m.target_team == "Legal" for m in matches)


def test_matching_escalation_rules_payment_dispute_cd_1011():
    """CD-1011 scenario: Payment dispute / chargeback escalates deterministically to Billing."""
    text = "I have filed a credit card chargeback and dispute with my bank for invoice #9921."
    matches = matching_escalation_rules(text=text, category=CategoryEnum.BILLING)
    assert len(matches) >= 1
    assert any(m.id == "RULE_PAYMENT_DISPUTE" and m.target_team == "Billing" for m in matches)


def test_matching_escalation_rules_enterprise_outage():
    """Active incident with enterprise customer escalates to Engineering."""
    text = "Users cannot authenticate into CloudDesk."
    matches = matching_escalation_rules(
        text=text,
        customer_plan="enterprise",
        is_active_outage=True,
    )
    assert len(matches) >= 1
    assert any(m.id == "RULE_ENTERPRISE_OUTAGE" and m.target_team == "Engineering" for m in matches)


def test_matching_escalation_rules_standard_ticket_no_match():
    """Standard inquiry does not match any escalation policy rules."""
    text = "How can I invite another team member to our workspace?"
    matches = matching_escalation_rules(text=text, category=CategoryEnum.WORKSPACE_PERMISSIONS)
    assert len(matches) == 0


# ---------------------------------------------------------------------------
# Severity Floor Rules Tests
# ---------------------------------------------------------------------------

def test_rule_severity_cannot_lower_model_severity():
    """Rules can raise model severity, but never lower it."""
    # Model proposed HIGH; rule evaluates standard text which has no floor
    result = rule_severity(
        text="Normal ticket question",
        model_severity=SeverityEnum.HIGH,
    )
    assert result == SeverityEnum.HIGH


def test_rule_severity_raises_for_enterprise_outage():
    """Active outage on enterprise customer raises severity to CRITICAL."""
    result = rule_severity(
        text="Service down",
        model_severity=SeverityEnum.LOW,
        customer_plan="enterprise",
        is_active_outage=True,
    )
    assert result == SeverityEnum.CRITICAL


def test_rule_severity_raises_for_security_incident():
    """Security breach text raises severity floor to HIGH."""
    result = rule_severity(
        text="Ransomware attack and compromised API keys",
        model_severity=SeverityEnum.LOW,
        category=CategoryEnum.SECURITY,
    )
    assert result in (SeverityEnum.HIGH, SeverityEnum.CRITICAL)


def test_rule_severity_raises_for_data_loss():
    """Critical data loss text raises severity floor to HIGH."""
    result = rule_severity(
        text="All customer production records were deleted and database is wiped",
        model_severity=SeverityEnum.MEDIUM,
    )
    assert result in (SeverityEnum.HIGH, SeverityEnum.CRITICAL)


def test_rule_severity_feature_request_default_low_cd_1010():
    """CD-1010: Feature requests have a default policy severity of LOW."""
    result = rule_severity(
        text="Please add dark mode theme to the web console",
        model_severity=SeverityEnum.LOW,
        category=CategoryEnum.FEATURE_REQUEST,
    )
    assert result == SeverityEnum.LOW


# ---------------------------------------------------------------------------
# Category Heuristic Rule Detection Tests
# ---------------------------------------------------------------------------

def test_rule_category_detection_patterns():
    """rule_category detects unambiguous category keywords across domain categories."""
    assert rule_category("SAML 2.0 SSO identity login failure") == CategoryEnum.LOGIN_ISSUE
    assert rule_category("Can I get an invoice or billing refund?") == CategoryEnum.BILLING
    assert rule_category("Rate limit 429 received from REST API endpoint") == CategoryEnum.API_FAILURE
    assert rule_category("Manage workspace member permissions and admin roles") == CategoryEnum.WORKSPACE_PERMISSIONS
    assert rule_category("Out of storage quota, upload limit exceeded") == CategoryEnum.STORAGE_QUOTA
    assert rule_category("Slack integration webhook fails to deliver") == CategoryEnum.INTEGRATION
    assert rule_category("Feature request: add dark mode to UI roadmap") == CategoryEnum.FEATURE_REQUEST
    assert rule_category("Account credentials compromised and security breach") == CategoryEnum.SECURITY


def test_rule_category_ambiguous_returns_none():
    """Ambiguous or generic text returns None, delegating judgment to the LLM."""
    assert rule_category("Hi there, I need some help today with our system.") is None


# ---------------------------------------------------------------------------
# Risk Assessment Tests
# ---------------------------------------------------------------------------

def test_assess_risk_high_for_policy_escalation():
    """assess_risk returns 'high' whenever escalation rules are triggered."""
    matches = [
        EscalationRule(
            id="RULE_SECURITY",
            name="Security Breach",
            target_team="Security",
            policy_reason="Account compromise",
        )
    ]
    risk = assess_risk(plan=None, matched_rules=matches)
    assert risk == "high"


def test_assess_risk_high_for_approval_gated_actions():
    """assess_risk returns 'high' when planned actions require approval (e.g. refund)."""
    plan = {
        "actions": [
            {"tool": "create_refund_request", "args": {"amount": 75.0}}
        ]
    }
    risk = assess_risk(plan=plan, matched_rules=[])
    assert risk == "high"


def test_assess_risk_low_for_safe_and_read_only_actions():
    """assess_risk returns 'low' when no policy escalation and only safe tools planned."""
    plan = {
        "actions": [
            {"tool": "update_ticket", "args": {"status": "in_progress"}},
            {"tool": "search_docs", "args": {"query": "SSO"}}
        ]
    }
    risk = assess_risk(plan=plan, matched_rules=[])
    assert risk == "low"


# ---------------------------------------------------------------------------
# Decision Evaluation: Distrusting Vague Model Escalations (AC-045)
# ---------------------------------------------------------------------------

def test_evaluate_escalation_decision_policy_rule_wins():
    """Policy rules always win over model opinion."""
    matches = [
        EscalationRule(
            id="RULE_GDPR_DELETION",
            name="GDPR Deletion",
            target_team="Legal",
            policy_reason="Right to be forgotten request",
        )
    ]
    # Model said NO escalation, but policy rule triggered
    decision = evaluate_escalation_decision(
        model_escalate=False,
        model_confidence=0.9,
        model_team="None",
        severity=SeverityEnum.MEDIUM,
        matched_rules=matches,
    )
    assert decision.escalation_required is True
    assert decision.target_team == "Legal"
    assert decision.rule_id == "RULE_GDPR_DELETION"


def test_evaluate_escalation_decision_distrusts_vague_model_escalation_ac_045():
    """AC-045: High severity but no matching policy rule and low model confidence rejects escalation."""
    decision = evaluate_escalation_decision(
        model_escalate=True,
        model_confidence=0.45,  # Low confidence (< 0.70)
        model_team="Engineering",
        severity=SeverityEnum.HIGH,
        matched_rules=[],  # No matching policy rule
    )
    # Escalation must be rejected
    assert decision.escalation_required is False
    assert decision.target_team is None


def test_evaluate_escalation_decision_accepts_confident_model_escalation():
    """When no policy rule matches but model has high confidence and valid team, accept it."""
    decision = evaluate_escalation_decision(
        model_escalate=True,
        model_confidence=0.88,  # High confidence
        model_team="Engineering",
        severity=SeverityEnum.HIGH,
        matched_rules=[],
    )
    assert decision.escalation_required is True
    assert decision.target_team == "Engineering"
    assert decision.rule_id is None


# ---------------------------------------------------------------------------
# Security & Penetration Testing (CWE Validation)
# ---------------------------------------------------------------------------

def test_security_cwe_862_model_cannot_override_policy_rule():
    """CWE-862: Hallucinated model refusal cannot bypass mandatory security escalation."""
    matches = [
        EscalationRule(
            id="RULE_SECURITY",
            name="Security Incident",
            target_team="Security",
            policy_reason="Compromised credentials detected",
        )
    ]
    # Model hallucinated that it can handle security breach without escalation
    decision = evaluate_escalation_decision(
        model_escalate=False,
        model_confidence=0.99,
        model_team="Support",
        severity=SeverityEnum.CRITICAL,
        matched_rules=matches,
    )
    assert decision.escalation_required is True
    assert decision.target_team == "Security"


def test_security_cwe_400_redos_and_oversized_payload_protection():
    """CWE-400: Oversized or crafted regex payload does not hang rule execution."""
    malicious_text = "account " * 10000 + "unauthorized!@#$%^&*() " * 5000
    # Must execute within normal limits without freezing
    matches = matching_escalation_rules(text=malicious_text)
    assert isinstance(matches, list)

    cat = rule_category(malicious_text)
    assert cat in (CategoryEnum.ACCOUNT, CategoryEnum.SECURITY)
