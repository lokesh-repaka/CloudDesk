---
title: "Troubleshooting SAML 2.0 Single Sign-On (SSO) Failures"
category: "login_issue"
tags: ["sso", "saml", "okta", "azure", "authentication"]
summary: "Guide to diagnosing and resolving SAML assertion signature errors and IdP configuration issues."
---

# Troubleshooting SAML 2.0 Single Sign-On (SSO) Failures

Enterprise accounts utilizing SAML 2.0 authentication may occasionally encounter login disruptions.

## Common Root Causes

1. **Expired IdP Signing Certificate**: The X.509 signing certificate in your Identity Provider (Okta, Azure AD, Google Workspace) has expired.
2. **Clock Skew**: System clock difference between your IdP server and CloudDesk exceeding the 180-second threshold.
3. **Mismatched Entity ID or ACS URL**: Ensure Assertion Consumer Service (ACS) is set to `https://auth.clouddesk.demo/sso/saml/acs`.

## Remediation Steps

1. Navigate to **Identity Provider Admin Settings > CloudDesk Application**.
2. Download the updated IdP metadata XML file or certificate.
3. Open **CloudDesk Admin Console > Security > Single Sign-On** and re-upload the valid certificate.
4. If an active platform incident is ongoing, monitor the status dashboard for service updates.
