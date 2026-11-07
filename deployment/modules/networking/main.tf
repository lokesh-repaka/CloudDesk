# ==============================================================================
# CloudDesk Infrastructure — Shared Module: Networking
# Provides VPC / VNet network boundaries, subnets, and routing rules (CLAUDE.md §15)
# ==============================================================================

terraform {
  required_version = ">= 1.5.0"
}

# Local resource placeholder / provider-abstracted network topology
locals {
  network_name = "${var.project_name}-${var.environment}-net"
}

