/*
  Glue Crawler data structure definition:

  Each object defines a Glue crawler that automatically discovers schema and partitions
  from data stored in S3. Crawlers populate the Glue Data Catalog with table metadata
  that can be queried via Athena.

  Required fields:
  - name (string): Short name for the crawler (will be prefixed with account-project-application)
  - database_name (string): Short name of the Glue database (references glue_databases)
  - s3_target_bucket (string): Short name of S3 bucket to crawl (references buckets)
  - iam_role_name (string): Short name of IAM role for crawler (references iam_roles)

  Optional fields:
  - description (string): Human-readable description (default: "")
  - s3_target_path (string): Path within bucket to crawl (default: "" for entire bucket)
  - schedule (string): Cron expression for crawler schedule (default: "" for manual only)
  - table_prefix (string): Prefix for created table names (default: "")

  Constraints:
  - database_name must reference an existing glue_database name
  - s3_target_bucket must reference an existing bucket name
  - iam_role_name must reference an existing iam_role name
  - schedule must be valid cron expression if specified
  - All names will be prefixed with account-project-application

  Example:
  {
    name               = "processed-data-crawler"
    database_name      = "analytics"
    s3_target_bucket   = "processed"
    iam_role_name      = "glue-crawler-role"
    description        = "Crawls processed Parquet files for schema discovery"
    s3_target_path     = ""
    schedule           = "cron(0 2 * * ? *)"  # Daily at 2 AM UTC
    table_prefix       = ""
  }
*/

locals {
  glue_crawlers = [
    {
      name             = "bookshelf-metadata-crawler"
      database_name    = "bookshelf"
      s3_target_bucket = "processed"
      iam_role_name    = "glue-crawler-role"
      description      = "Automatically discovers schema and partitions from book metadata Parquet files"
      s3_target_path   = "processed/"
      schedule         = "cron(0 3 * * ? *)" # Daily at 3 AM UTC
      table_prefix     = ""
    }
  ]
}
