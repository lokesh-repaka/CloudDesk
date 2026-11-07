# ==============================================================================
# CloudDesk Infrastructure — Shared Module: Load Balancer
# Application Load Balancer / App Gateway with health check routing
# ==============================================================================

terraform {
  required_version = ">= 1.5.0"
}

locals {
  alb_name = "${var.project_name}-${var.environment}-alb"
}

