# Create all Athena workgroups defined in the data module
resource "aws_athena_workgroup" "workgroup" {
  for_each = { for wg in module.data.athena_workgroups : wg.name => wg }

  name        = each.value.full_name
  description = each.value.description

  configuration {
    result_configuration {
      output_location = each.value.results_s3_path
    }

    publish_cloudwatch_metrics_enabled = each.value.publish_cloudwatch_metrics_enabled
    bytes_scanned_cutoff_per_query     = each.value.bytes_scanned_cutoff_per_query
  }

  # Ensure results bucket exists before creating workgroup
  depends_on = [aws_s3_bucket.bucket]
}
