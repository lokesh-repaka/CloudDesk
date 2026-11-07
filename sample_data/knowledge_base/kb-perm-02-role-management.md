---
title: "Role Hierarchy and Access Control: Viewer, Agent, and Admin"
category: "workspace_permissions"
tags: ["roles", "rbac", "permissions", "viewer", "agent", "admin"]
summary: "Detailed breakdown of platform role capabilities, privileges, and inheritance rules."
---

# Role Hierarchy and Access Control: Viewer, Agent, and Admin

CloudDesk enforces strict Role-Based Access Control (RBAC) across both API and database layers:

## Role Hierarchy

1. **Viewer (`viewer`)**:
   - Read-only auditor privileges.
   - Can inspect tickets, workspaces, articles, and audit records.
   - Strictly prohibited from updating status, approving actions, or triggering workflows.
2. **Agent (`agent`)**:
   - Customer support specialist.
   - Can invoke workflows, reply to customers, request approvals, and escalate tickets.
3. **Admin (`admin`)**:
   - Platform administrator.
   - Full access including reindexing knowledge base, modifying settings, and issuing refunds.
