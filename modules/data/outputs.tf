# Default values outputs
output "account" {
  description = "Default account identifier"
  value       = local.account
}

output "project" {
  description = "Default project identifier"
  value       = local.project
}

output "application" {
  description = "Default application identifier"
  value       = local.application
}

output "environment" {
  description = "Deployment environment"
  value       = local.environment
}

output "lambda_defaults" {
  description = "Default Lambda configuration values"
  value       = local.lambda_defaults
}

output "s3_defaults" {
  description = "Default S3 bucket configuration values"
  value       = local.s3_defaults
}

output "notification_defaults" {
  description = "Default notification configuration values"
  value       = local.notification_defaults
}

# Enriched infrastructure outputs
output "buckets" {
  description = "All S3 buckets with enriched metadata and computed values"
  value       = local.buckets_enriched
}

output "buckets_map" {
  description = "Map of S3 buckets keyed by bucket name"
  value       = local.buckets_map
}

output "layers" {
  description = "All Lambda layers with enriched metadata and computed values"
  value       = local.layers_enriched
}

output "layers_map" {
  description = "Map of Lambda layers keyed by layer name"
  value       = local.layers_map
}

output "lambdas" {
  description = "All Lambda functions with enriched metadata and computed values"
  value       = local.lambdas_enriched
}

output "lambdas_map" {
  description = "Map of Lambda functions keyed by function name"
  value       = local.lambdas_map
}

output "notifications" {
  description = "All S3 notifications with resolved references"
  value       = local.notifications_enriched
}

output "notifications_map" {
  description = "Map of notifications keyed by bucket name"
  value       = local.notifications_map
}

output "glue_databases" {
  description = "All Glue databases with enriched metadata and computed values"
  value       = local.glue_databases_enriched
}

output "glue_databases_map" {
  description = "Map of Glue databases keyed by database name"
  value       = local.glue_databases_map
}

output "glue_crawlers" {
  description = "All Glue crawlers with resolved references"
  value       = local.glue_crawlers_enriched
}

output "glue_crawlers_map" {
  description = "Map of Glue crawlers keyed by crawler name"
  value       = local.glue_crawlers_map
}

output "athena_workgroups" {
  description = "All Athena workgroups with resolved references"
  value       = local.athena_workgroups_enriched
}

output "glue_security_config_name" {
  description = "Name for the Glue security configuration resource"
  value       = local.glue_security_config_name
}

output "athena_workgroups_map" {
  description = "Map of Athena workgroups keyed by workgroup name"
  value       = local.athena_workgroups_map
}

output "dynamodb_tables" {
  description = "All DynamoDB tables with enriched metadata and computed values"
  value       = local.dynamodb_tables_enriched
}

output "dynamodb_tables_map" {
  description = "Map of DynamoDB tables keyed by table name"
  value       = local.dynamodb_tables_map
}

output "step_functions" {
  description = "All Step Functions state machines with enriched metadata and computed values"
  value       = local.step_functions_enriched
}

output "step_functions_map" {
  description = "Map of Step Functions state machines keyed by name"
  value       = local.step_functions_map
}
