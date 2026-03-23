resource "aws_athena_workgroup" "workgroup" {
  for_each = { for wg in var.workgroups : wg.name => wg }

  name          = each.value.full_name
  description   = each.value.description
  force_destroy = true

  configuration {
    result_configuration {
      output_location = each.value.results_s3_path

      encryption_configuration {
        encryption_option = "SSE_S3"
      }
    }

    publish_cloudwatch_metrics_enabled = each.value.publish_cloudwatch_metrics_enabled
    bytes_scanned_cutoff_per_query     = each.value.bytes_scanned_cutoff_per_query
  }
}
