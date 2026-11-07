variable "gcp_project_id" {
  description = "GCP Project ID"
  type        = string
  default     = "clouddesk-project"
}

variable "gcp_region" {
  description = "Target GCP deployment region"
  type        = string
  default     = "us-central1"
}

variable "project_name" {
  description = "Project name identifier"
  type        = string
  default     = "clouddesk"
}

variable "environment" {
  description = "Target environment: dev, staging, prod"
  type        = string
}

variable "image_tag" {
  description = "Container image tag matching git commit SHA"
  type        = string
  default     = "latest"
}

variable "cidr_block" {
  description = "VPC Subnet CIDR block"
  type        = string
  default     = "10.0.0.0/16"
}
