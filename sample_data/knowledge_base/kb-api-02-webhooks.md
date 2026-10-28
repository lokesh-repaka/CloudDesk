---
title: "Webhook Delivery Retries and Signature Verification"
category: "api_failure"
tags: ["api", "webhooks", "signatures", "retries", "integrations"]
summary: "Verifying webhook HMAC signatures and diagnosing webhook delivery failures."
---

# Webhook Delivery Retries and Signature Verification

CloudDesk dispatches asynchronous HTTP POST notifications when state changes occur on tickets, workflows, and incidents.

## Signature Verification

Every webhook payload includes the `X-CloudDesk-Signature` header computed using HMAC SHA-256 with your workspace webhook secret key.

## Retry Policy

If the target endpoint does not return HTTP 2xx within 5,000 ms:
- CloudDesk retries delivery with exponential backoff: 30s, 2m, 10m, 1h, 6h.
- After 5 consecutive failures, the webhook endpoint is temporarily disabled to protect recipient infrastructure.
