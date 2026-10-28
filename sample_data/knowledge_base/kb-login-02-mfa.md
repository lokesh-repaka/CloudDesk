---
title: "Multi-Factor Authentication (MFA) Recovery and Device Reset"
category: "login_issue"
tags: ["mfa", "totp", "lockout", "authenticator", "security"]
summary: "Procedures for resetting MFA devices when locked out after failed verification attempts."
---

# Multi-Factor Authentication (MFA) Recovery and Device Reset

When users lose access to their authenticator app or replace their physical device, MFA lockout protection engages after 5 consecutive failed attempts.

## Recovery Workflow

1. **Self-Service Backup Codes**: If you saved your 8-digit emergency recovery codes during initial MFA enrollment, click "Use Recovery Code" on the login prompt.
2. **Organization Administrator Reset**: An organization admin can reset a member's MFA by navigating to **Team Management > Members > [User] > Security Actions > Reset MFA**.
3. **Identity Verification**: If you are the sole administrator on the account, contact CloudDesk Support with your verified domain DNS TXT token to complete an out-of-band identity check.
