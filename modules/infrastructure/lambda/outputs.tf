output "function_arns" {
  description = "Map of function short name to ARN"
  value       = { for name, f in aws_lambda_function.function : name => f.arn }
}

output "function_names" {
  description = "Map of function short name to full function name"
  value       = { for name, f in aws_lambda_function.function : name => f.function_name }
}

output "role_arns" {
  description = "Map of function short name to IAM role ARN"
  value       = { for name, r in aws_iam_role.lambda : name => r.arn }
}
