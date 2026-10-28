---
title: "Security Telemetry, Audit Trails, and Prompt Injection Defense"
category: "security"
tags: ["security", "audit", "injection", "guardrails", "compliance"]
summary: "System design for immutable audit logging and prompt injection containment."
---

# Security Telemetry, Audit Trails, and Prompt Injection Defense

All state-changing operations across the CloudDesk platform produce immutable audit rows in `audit_logs`.

## Prompt Injection Defense

Incoming ticket messages, email contents, and webhook payloads are considered **untrusted external data**.
- All customer text is wrapped inside `<untrusted_content>` tags before LLM consumption.
- System prompts are protected with the `SECURITY_PREAMBLE` prohibiting models from treating data strings as procedural instructions.
- System commands, debug overrides, and prompt injection attempts remain safely treated as conversational text.
