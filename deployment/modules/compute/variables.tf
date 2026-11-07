variable "project_name" {
  description = "Project name identifier"
  type        = string
  default     = "clouddesk"
}

variable "environment" {
  description = "Target deployment environment (dev, staging, prod)"
  type        = string
}

variable "image_tag" {
  description = "Container image tag (must match git commit SHA per CLAUDE.md §15)"
  type        = string
  default     = "latest"
}

variable "cpu" {
  description = "Allocated CPU units"
  type        = string
  default     = "512"
}

variable "memory" {
  description = "Allocated memory in MB"
  type        = string
  default     = "1024"
}
