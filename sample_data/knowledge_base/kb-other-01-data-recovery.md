---
title: "Data Loss Prevention, Accidental Deletion, and Point-in-Time Recovery"
category: "other"
tags: ["other", "data-loss", "recovery", "backups", "disaster-recovery"]
summary: "Procedures for reporting missing files, investigating data loss, and initiating backup restores."
---

# Data Loss Prevention, Accidental Deletion, and Point-in-Time Recovery

Unexplained file disappearances or suspected data loss incidents require immediate technical investigation.

## Data Loss Escalation Protocol

When a customer reports:
- Missing workspace folders without user deletion records in audit logs
- Unexplained file corruption across shared directories
- Database synchronization anomalies

The incident **MUST BE ESCALATED IMMEDIATELY** to the **Infrastructure & Storage Reliability** engineering team.

## Automated Snapshots and Recovery

- All CloudDesk enterprise workspaces take automated point-in-time snapshots every 60 minutes.
- Snapshots are retained for 14 days in geographically redundant multi-region storage.
- Support engineers can restore workspaces to any recorded snapshot timestamp prior to the incident.
