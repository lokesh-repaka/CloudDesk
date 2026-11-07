variable "project_name" {
  description = "Project name identifier"
  type        = string
  default     = "clouddesk"
}

variable "environment" {
  description = "Target deployment environment (dev, staging, prod)"
  type        = string
}

variable "image_tag_mutability" {
  description = "Tag mutability setting (IMMUTABLE recommended for production)"
  type        = string
  default     = "IMMUTABLE"
}
