output "redis_cluster_id" {
  description = "Managed Redis cluster identifier"
  value       = local.redis_cluster_id
}

output "node_type" {
  description = "Redis node type"
  value       = var.node_type
}

