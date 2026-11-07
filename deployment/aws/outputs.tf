output "alb_endpoint" {
  description = "Public ALB DNS endpoint"
  value       = module.load_balancer.load_balancer_name
}

output "backend_repository_url" {
  description = "AWS ECR backend repository URL"
  value       = module.container_registry.backend_repository
}

output "frontend_repository_url" {
  description = "AWS ECR frontend repository URL"
  value       = module.container_registry.frontend_repository
}

