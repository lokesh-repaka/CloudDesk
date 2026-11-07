# ==============================================================================
# CloudDesk Infrastructure — Shared Module: Secrets Management
# AWS Secrets Manager / Azure Key Vault / GCP Secret Manager boundary
# Enforces TF_VAR_* injection without committing secrets (CLAUDE.md §15, CWE-200)
# ==============================================================================

terraform {
  required_version = ">= 1.5.0"
}

locals {
  secret_vault_name = "${var.project_name}-${var.environment}-secrets"
}
