---
title: "API Rate Limits, HTTP 429 Errors, and Backoff Guidelines"
category: "api_failure"
tags: ["api", "rate-limit", "429", "backoff", "throttling"]
summary: "Understanding CloudDesk REST API rate limits and implementing exponential backoff."
---

# API Rate Limits, HTTP 429 Errors, and Backoff Guidelines

All API requests are throttled using a token bucket rate limiter to preserve service stability.

## Standard Rate Limit Ceilings

- **Demo / Free Tier**: 120 requests per minute
- **Pro Tier**: 600 requests per minute
- **Business Tier**: 1,800 requests per minute
- **Enterprise Tier**: 6,000 requests per minute (customizable via Enterprise SLA)

## Handling HTTP 429 Responses

When a client exceeds the allocated limit, the server responds with:
- `HTTP 429 Too Many Requests`
- `Retry-After: <seconds>` header indicating the cool-off duration.

Clients should implement exponential backoff with jitter and utilize bulk endpoints (`/api/v1/tickets/batch`) for synchronization workloads.
