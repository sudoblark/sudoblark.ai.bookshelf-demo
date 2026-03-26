output "tables" {
  description = "Map of created DynamoDB tables keyed by logical name"
  value       = { for k, v in aws_dynamodb_table.table : k => v }
}

output "tables_map" {
  description = "Map of DynamoDB table names (logical name => full table name)"
  value       = { for k, v in aws_dynamodb_table.table : k => v.name }
}
