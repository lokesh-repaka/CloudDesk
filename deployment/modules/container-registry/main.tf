# ==============================================================================
# CloudDesk Infrastructure — Shared Module: Container Registry
# ECR / ACR / Artifact Registry configuration for immutable image storage
# ==============================================================================

terraform {
  required_version = ">= 1.5.0"
}

locals {
  backend_repo_name  = "${var.project_name}-${var.environment}-backend"
  frontend_repo_name = "${var.project_name}-${var.environment}-frontend"
}
