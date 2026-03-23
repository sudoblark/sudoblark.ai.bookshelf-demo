variable "notifications" {
  description = "Enriched list of S3 bucket notifications"
  type = list(object({
    bucket_name = string
    lambda_notifications_resolved = list(object({
      lambda_name         = string
      lambda_function_arn = string
      events              = list(string)
      filter_prefix       = string
      filter_suffix       = string
    }))
  }))
}

variable "bucket_ids" {
  description = "Map of bucket short name to S3 resource ID (from s3 module output)"
  type        = map(string)
}

variable "bucket_arns" {
  description = "Map of bucket short name to S3 bucket ARN (from s3 module output)"
  type        = map(string)
}
