variable "project_name" {
  description = "Project name identifier"
  type        = string
  default     = "clouddesk"
}

variable "environment" {
  description = "Target deployment environment (dev, staging, prod)"
  type        = string
}

variable "node_type" {
  description = "Redis compute instance node type"
  type        = string
  default     = "cache.t4g.micro"
}
