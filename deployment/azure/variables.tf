variable "azure_location" {
  description = "Target Azure region"
  type        = string
  default     = "eastus"
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
  description = "VNet address space CIDR"
  type        = string
  default     = "10.0.0.0/16"
}
