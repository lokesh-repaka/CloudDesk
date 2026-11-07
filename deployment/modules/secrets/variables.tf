variable "project_name" {
  description = "Project name identifier"
  type        = string
  default     = "clouddesk"
}

variable "environment" {
  description = "Target deployment environment (dev, staging, prod)"
  type        = string
}

variable "secret_names" {
  description = "List of secret identifiers managed in vault"
  type        = list(string)
  default     = ["jwt_secret", "database_password", "redis_password"]
}

