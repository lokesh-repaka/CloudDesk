variable "project_name" {
  description = "Project name identifier"
  type        = string
  default     = "clouddesk"
}

variable "environment" {
  description = "Target deployment environment (dev, staging, prod)"
  type        = string
}

variable "cidr_block" {
  description = "Primary CIDR block for VPC / VNet"
  type        = string
  default     = "10.0.0.0/16"
}

