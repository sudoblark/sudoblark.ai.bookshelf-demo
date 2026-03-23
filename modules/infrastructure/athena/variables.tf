variable "workgroups" {
  description = "Enriched list of Athena workgroups to create"
  type = list(object({
    name                               = string
    full_name                          = string
    description                        = string
    results_s3_path                    = string
    publish_cloudwatch_metrics_enabled = bool
    bytes_scanned_cutoff_per_query     = number
  }))
}
