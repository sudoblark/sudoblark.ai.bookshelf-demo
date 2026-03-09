/*
  Athena Workgroup data structure definition:

  Each object defines an Athena workgroup for organizing and controlling query execution.
  Workgroups manage query output locations, cost controls, and execution settings.

  Required fields:
  - name (string): Short name for the workgroup (will be prefixed with account-project-application)
  - results_bucket (string): Short name of S3 bucket for query results (references buckets)

  Optional fields:
  - description (string): Human-readable description (default: "")
  - publish_cloudwatch_metrics_enabled (bool): Publish metrics to CloudWatch (default: true)
  - bytes_scanned_cutoff_per_query (number): Per-query data scan limit in bytes (default: 0 for no limit)

  Constraints:
  - results_bucket must reference an existing bucket name
  - name will be prefixed with account-project-application
  - bytes_scanned_cutoff_per_query must be non-negative (0 means no limit)

  Example:
  {
    name                                 = "analytics-workgroup"
    results_bucket                       = "athena-results"
    description                          = "Workgroup for analytics queries on ETL pipeline data"
    publish_cloudwatch_metrics_enabled   = true
    bytes_scanned_cutoff_per_query       = 0
  }
*/

locals {
  athena_workgroups = [
    {
      name                               = "bookshelf-analytics"
      results_bucket                     = "athena-results"
      description                        = "Workgroup for querying book metadata from processed Parquet files"
      publish_cloudwatch_metrics_enabled = true
      bytes_scanned_cutoff_per_query     = 0 # No limit
    }
  ]
}
