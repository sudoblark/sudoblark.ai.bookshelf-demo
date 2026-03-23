output "bucket_ids" {
  description = "Map of bucket short name to resource ID"
  value       = { for name, b in aws_s3_bucket.bucket : name => b.id }
}

output "bucket_arns" {
  description = "Map of bucket short name to ARN"
  value       = { for name, b in aws_s3_bucket.bucket : name => b.arn }
}
