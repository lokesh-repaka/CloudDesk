# ==============================================================================
# CloudDesk Infrastructure — Shared Module: Compute
# Serverless / container execution platform (ECS Fargate / Container Apps / Cloud Run)
# ==============================================================================

terraform {
  required_version = ">= 1.5.0"
}

locals {
  backend_service_name  = "${var.project_name}-${var.environment}-backend-svc"
  frontend_service_name = "${var.project_name}-${var.environment}-frontend-svc"
}

