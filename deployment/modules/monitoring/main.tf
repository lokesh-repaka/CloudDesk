# ==============================================================================
# CloudDesk Infrastructure — Shared Module: Monitoring & Observability
# CloudWatch / Log Analytics / Cloud Logging and alert alarms (CLAUDE.md §16)
# ==============================================================================

terraform {
  required_version = ">= 1.5.0"
}

locals {
  log_group_name = "/clouddesk/${var.environment}/logs"
}
