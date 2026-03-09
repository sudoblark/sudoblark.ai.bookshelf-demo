output "bucket_names" {
  description = "Map of bucket short names to full bucket names"
  value = {
    for bucket in module.data.buckets :
    bucket.name => bucket.full_name
  }
}

output "lambda_function_arns" {
  description = "Map of Lambda function names to ARNs"
  value = {
    for name, lambda in aws_lambda_function.lambda :
    name => lambda.arn
  }
}
