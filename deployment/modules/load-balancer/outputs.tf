output "load_balancer_name" {
  description = "Name of the provisioned load balancer"
  value       = local.alb_name
}

output "health_check_path" {
  description = "Configured health check path"
  value       = var.health_check_path
}

