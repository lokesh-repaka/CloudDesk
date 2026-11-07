# ==============================================================================
# CloudDesk Infrastructure — Azure Root (CLAUDE.md §15)
# Composes shared modules for Azure deployment:
# ACR / Container Apps / Key Vault / Log Analytics / Azure Cache for Redis
# ==============================================================================

terraform {
  required_version = ">= 1.5.0"
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.0"
    }
  }
  # Remote state backend configured via backend.hcl (CLAUDE.md §15)
  backend "azurerm" {}
}

provider "azurerm" {
  features {}
}

module "networking" {
  source       = "../modules/networking"
  project_name = var.project_name
  environment  = var.environment
  cidr_block   = var.cidr_block
}

module "container_registry" {
  source       = "../modules/container-registry"
  project_name = var.project_name
  environment  = var.environment
}

module "secrets" {
  source       = "../modules/secrets"
  project_name = var.project_name
  environment  = var.environment
}

module "compute" {
  source       = "../modules/compute"
  project_name = var.project_name
  environment  = var.environment
  image_tag    = var.image_tag
}

module "load_balancer" {
  source       = "../modules/load-balancer"
  project_name = var.project_name
  environment  = var.environment
}

module "monitoring" {
  source       = "../modules/monitoring"
  project_name = var.project_name
  environment  = var.environment
}

module "redis" {
  source       = "../modules/redis"
  project_name = var.project_name
  environment  = var.environment
}
