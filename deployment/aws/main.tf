# ==============================================================================
# CloudDesk Infrastructure — AWS Root (CLAUDE.md §15)
# Composes shared modules for AWS deployment:
# ECR / ECS Fargate / ALB / Secrets Manager / CloudWatch / ElastiCache Redis
# ==============================================================================

terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
  # Remote state backend configured via backend.hcl (CLAUDE.md §15)
  backend "s3" {}
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = var.project_name
      Environment = var.environment
      ManagedBy   = "Terraform"
    }
  }
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
