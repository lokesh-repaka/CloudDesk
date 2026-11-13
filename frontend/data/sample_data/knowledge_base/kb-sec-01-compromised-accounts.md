---
title: "Incident Response Protocol for Compromised Accounts and Breaches"
category: "security"
tags: ["security", "breach", "compromise", "escalation", "incident-response"]
summary: "High-priority response procedure for reported account takeover or anomalous access."
---

# Incident Response Protocol for Compromised Accounts and Breaches

CloudDesk maintains a zero-tolerance policy for suspected account compromises.

## Mandatory Escalation Rule

When a customer reports:
- Suspicious logins from unrecognized foreign IP addresses
- Phishing, credential stuffing, or session hijacking
- Unauthorized changes to API keys or administrative members

The ticket **MUST BE IMMEDIATELY ESCALATED** to the **Security Operations Center (SOC)**.

## Autonomous Agent Safeguards

AI agents encountering security breach reports:
1. Elevate ticket severity to `critical`.
2. Do not attempt self-service automated password reset responses.
3. Lock active API session tokens when authorized by policy.
4. Notify the on-call Security Lead within 15 minutes.
