---
title: "Workspace Storage Quotas and Storage Tier Specifications"
category: "storage_quota"
tags: ["storage", "quota", "tiers", "limits", "upgrade"]
summary: "Overview of workspace storage quota allowances and tier upgrade processes."
---

# Workspace Storage Quotas and Storage Tier Specifications

Storage allocations are enforced per workspace according to the customer's subscription plan.

## Storage Capacity by Tier

- **Free Tier**: 1 GB total storage
- **Pro Tier**: 10 GB total storage
- **Business Tier**: 25 GB total storage
- **Enterprise Tier**: 50 GB default storage (scalable to petabytes upon request)

## Quota Enforcement Behavior

When a workspace reaches 100% of its storage capacity:
- Write operations return `HTTP 413 Payload Too Large` or `Storage Quota Exceeded`.
- Existing files remain fully accessible for download and read-only inspection.
- Upgrading the plan or purging deleted items immediately re-enables uploads.
