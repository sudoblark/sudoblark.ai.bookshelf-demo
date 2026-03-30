data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

locals {
  # Enrich S3 buckets with computed full names and merged defaults
  buckets_enriched = [
    for bucket in local.buckets : merge(
      {
        account      = local.account
        project      = local.project
        application  = local.application
        folder_paths = local.s3_defaults.folder_paths
      },
      bucket,
      {
        # Computed full bucket name following naming convention
        full_name = lower("${local.account}-${local.project}-${local.application}-${bucket.name}")
      }
    )
  ]

  # Create a map of buckets keyed by name for easy lookup
  buckets_map = {
    for bucket in local.buckets_enriched : bucket.name => bucket
  }

  # Enrich Lambda Layers with computed values and merged defaults
  layers_enriched = [
    for layer in local.layers : merge(
      {
        account             = local.account
        project             = local.project
        application         = local.application
        description         = local.layer_defaults.description
        compatible_runtimes = local.layer_defaults.compatible_runtimes
      },
      layer,
      {
        # Computed full layer name following naming convention
        full_name = lower("${local.account}-${local.project}-${local.application}-${layer.name}")
      }
    )
  ]

  # Create a map of Layers keyed by name for easy lookup
  layers_map = {
    for layer in local.layers_enriched : layer.name => layer
  }

  # Enrich Lambda functions with computed values and merged defaults
  lambdas_enriched = [
    for lambda in local.lambdas : merge(
      {
        account               = local.account
        project               = local.project
        application           = local.application
        runtime               = local.lambda_defaults.runtime
        timeout               = local.lambda_defaults.timeout
        memory_size           = local.lambda_defaults.memory_size
        layers                = local.lambda_defaults.layers
        layer_names           = local.lambda_defaults.layer_names
        environment_variables = local.lambda_defaults.environment_variables
      },
      lambda,
      {
        # Computed full Lambda function name
        full_name = lower("${local.account}-${local.project}-${local.application}-${lambda.name}")
        # Computed IAM role name — created by the lambda infrastructure module
        role_name = lower("${local.account}-${local.project}-${local.application}-${lambda.name}")
      }
    )
  ]

  # Create a map of Lambdas keyed by name for easy lookup
  lambdas_map = {
    for lambda in local.lambdas_enriched : lambda.name => lambda
  }

  # Enrich notifications with resolved references
  notifications_enriched = [
    for notification in local.notifications : merge(
      notification,
      {
        # Resolved bucket ID from bucket name
        bucket_id = local.buckets_map[notification.bucket_name].full_name
        # Enrich lambda notifications with resolved ARNs
        lambda_notifications_resolved = [
          for lambda_notif in notification.lambda_notifications : merge(
            {
              events        = local.notification_defaults.events
              filter_prefix = ""
              filter_suffix = ""
            },
            lambda_notif,
            {
              # Resolve Lambda ARN from lambda name
              lambda_function_arn = "arn:aws:lambda:${data.aws_region.current.id}:${data.aws_caller_identity.current.account_id}:function:${local.lambdas_map[lambda_notif.lambda_name].full_name}"
            }
          )
        ]
      }
    )
  ]

  # Create a map of notifications keyed by bucket name
  notifications_map = {
    for notification in local.notifications_enriched : notification.bucket_name => notification
  }

  # Enrich Glue databases with computed full names
  glue_databases_enriched = [
    for db in local.glue_databases : merge(
      {
        account     = local.account
        project     = local.project
        application = local.application
        description = ""
      },
      db,
      {
        # Computed full database name
        full_name = lower("${local.account}-${local.project}-${local.application}-${db.name}")
      }
    )
  ]

  # Create a map of Glue databases keyed by name
  glue_databases_map = {
    for db in local.glue_databases_enriched : db.name => db
  }

  # Enrich Glue crawlers with resolved references
  glue_crawlers_enriched = [
    for crawler in local.glue_crawlers : merge(
      {
        account        = local.account
        project        = local.project
        application    = local.application
        description    = ""
        s3_target_path = ""
        schedule       = ""
        table_prefix   = ""
      },
      crawler,
      {
        # Computed full crawler name
        full_name = lower("${local.account}-${local.project}-${local.application}-${crawler.name}")
        # Resolved database name from reference
        database_full_name = local.glue_databases_map[crawler.database_name].full_name
        # Resolved S3 target path
        s3_target_full_path = "s3://${local.buckets_map[crawler.s3_target_bucket].full_name}${crawler.s3_target_path != "" ? "/${crawler.s3_target_path}" : ""}"
        # Computed IAM role name — created by the glue infrastructure module
        role_name = lower("${local.account}-${local.project}-${local.application}-${crawler.name}")
      }
    )
  ]

  # Create a map of Glue crawlers keyed by name
  glue_crawlers_map = {
    for crawler in local.glue_crawlers_enriched : crawler.name => crawler
  }

  # Enrich Athena workgroups with resolved references
  athena_workgroups_enriched = [
    for wg in local.athena_workgroups : merge(
      {
        account                            = local.account
        project                            = local.project
        application                        = local.application
        description                        = ""
        publish_cloudwatch_metrics_enabled = true
        bytes_scanned_cutoff_per_query     = 0
      },
      wg,
      {
        # Computed full workgroup name
        full_name = lower("${local.account}-${local.project}-${local.application}-${wg.name}")
        # Resolved results bucket S3 path
        results_s3_path = "s3://${local.buckets_map[wg.results_bucket].full_name}/"
      }
    )
  ]

  # Create a map of Athena workgroups keyed by name
  athena_workgroups_map = {
    for wg in local.athena_workgroups_enriched : wg.name => wg
  }

  # Enrich DynamoDB tables with computed full names
  dynamodb_tables_enriched = [
    for table in local.dynamodb_tables : merge(
      {
        account      = local.account
        project      = local.project
        application  = local.application
        billing_mode = "PAY_PER_REQUEST"
      },
      table,
      {
        # Computed full table name following naming convention
        full_name = lower("${local.account}-${local.project}-${local.application}-${table.name}")
      }
    )
  ]

  # Create a map of DynamoDB tables keyed by name
  dynamodb_tables_map = {
    for table in local.dynamodb_tables_enriched : table.name => table
  }

  # Glue security configuration name
  glue_security_config_name = "${local.account}-glue-security-config"

  # Enrich Step Functions state machines with computed values and resolved references
  step_functions_enriched = [
    for sm in local.step_functions : merge(
      {
        account     = local.account
        project     = local.project
        application = local.application
        description = ""
      },
      sm,
      {
        # Computed full state machine name following naming convention
        full_name = lower("${local.account}-${local.project}-${local.application}-${sm.name}")
        # Computed IAM role name — created by the step_functions infrastructure module
        role_name = lower("${local.account}-${local.project}-${local.application}-${sm.name}")
        # Resolved metadata-extractor Lambda ARN from lambda name reference
        metadata_extractor_arn = "arn:aws:lambda:${data.aws_region.current.id}:${data.aws_caller_identity.current.account_id}:function:${local.lambdas_map[sm.metadata_extractor_name].full_name}"
      }
    )
  ]

  # Create a map of Step Functions state machines keyed by name
  step_functions_map = {
    for sm in local.step_functions_enriched : sm.name => sm
  }
}
