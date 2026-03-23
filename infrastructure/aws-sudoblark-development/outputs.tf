output "bucket_names" {
  description = "Map of bucket short names to full bucket names"
  value       = module.s3.bucket_ids
}

output "lambda_function_arns" {
  description = "Map of Lambda function names to ARNs"
  value       = module.lambda.function_arns
}

output "lambda_role_arns" {
  description = "Map of Lambda function names to IAM role ARNs"
  value       = module.lambda.role_arns
}

output "glue_database_names" {
  description = "Map of Glue database short names to full catalog database names"
  value       = module.glue.database_names
}

output "athena_workgroup_names" {
  description = "Map of Athena workgroup short names to full workgroup names"
  value       = module.athena.workgroup_names
}
