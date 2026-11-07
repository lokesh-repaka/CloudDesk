output "app_gateway_endpoint" {
  description = "Public Azure Application Gateway DNS"
  value       = module.load_balancer.load_balancer_name
}

output "acr_login_server" {
  description = "Azure Container Registry login server"
  value       = module.container_registry.backend_repository
}

