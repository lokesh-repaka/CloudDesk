output "vault_name" {
  description = "Secrets vault identifier"
  value       = local.secret_vault_name
}

output "managed_secrets" {
  description = "Identifiers of managed secrets"
  value       = var.secret_names
}

