output "network_name" {
  description = "Name of the provisioned network boundary"
  value       = local.network_name
}

output "cidr_block" {
  description = "Assigned CIDR block"
  value       = var.cidr_block
}
