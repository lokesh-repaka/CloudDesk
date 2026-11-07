output "cloud_run_endpoint" {
  description = "Cloud Run service URL"
  value       = module.load_balancer.load_balancer_name
}

output "artifact_registry_repository" {
  description = "GCP Artifact Registry repository identifier"
  value       = module.container_registry.backend_repository
}

