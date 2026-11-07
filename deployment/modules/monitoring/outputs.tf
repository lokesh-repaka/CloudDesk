output "log_group" {
  description = "Centralized log group / log analytics workspace identifier"
  value       = local.log_group_name
}

output "retention_days" {
  description = "Configured retention days"
  value       = var.retention_in_days
}

