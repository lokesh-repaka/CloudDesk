---
title: "Connecting Slack Notifications and Webhook Troubleshooting"
category: "integration"
tags: ["integration", "slack", "webhooks", "alerts", "bot"]
summary: "Setup guide and troubleshooting steps for the CloudDesk Slack notification bot."
---

# Connecting Slack Notifications and Webhook Troubleshooting

The CloudDesk Slack app dispatches real-time ticket creation, escalation, and approval notifications to designated Slack channels.

## Common Connection Issues

1. **Invalid or Expired OAuth Token**: If Slack workspace administrators rotate app permissions, the CloudDesk integration token may be revoked.
2. **Missing Channel Permissions**: The `@CloudDesk Bot` must be invited to private Slack channels (`/invite @CloudDesk`).

## Re-authenticating Slack

1. Navigate to **Integrations > Slack**.
2. Click **Reconnect to Slack** to complete the OAuth 2.0 authorization flow.
3. Select the target notification channel and click **Test Alert**.
