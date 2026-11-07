variable "project_name" {
  description = "Project name identifier"
  type        = string
  default     = "clouddesk"
}

variable "environment" {
  description = "Target deployment environment (dev, staging, prod)"
  type        = string
}

variable "health_check_path" {
  description = "Path for ALB health check probe"
  type        = string
  default     = "/health/live"
}

