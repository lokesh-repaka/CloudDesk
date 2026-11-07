# ==============================================================================
# CloudDesk Infrastructure — Shared Module: Redis
# Managed ElastiCache / Azure Cache / Memorystore for short-term memory & locks
# ==============================================================================

terraform {
  required_version = ">= 1.5.0"
}

locals {
  redis_cluster_id = "${var.project_name}-${var.environment}-redis"
}

