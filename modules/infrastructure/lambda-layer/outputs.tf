output "layer_arns" {
  description = "Map of layer short name to ARN (including version)"
  value       = { for name, layer in aws_lambda_layer_version.layer : name => layer.arn }
}
