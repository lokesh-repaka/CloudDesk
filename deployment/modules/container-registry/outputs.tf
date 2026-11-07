output "backend_repository" {
  description = "Backend container repository identifier"
  value       = local.backend_repo_name
}

output "frontend_repository" {
  description = "Frontend container repository identifier"
  value       = local.frontend_repo_name
}
