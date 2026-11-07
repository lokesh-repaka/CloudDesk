output "backend_service" {
  description = "Backend compute service name"
  value       = local.backend_service_name
}

output "frontend_service" {
  description = "Frontend compute service name"
  value       = local.frontend_service_name
}

