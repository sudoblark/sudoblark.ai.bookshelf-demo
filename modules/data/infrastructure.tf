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

  # Enrich Lambda functions with computed values and merged defaults
  lambdas_enriched = [
    for lambda in local.lambdas : merge(
      {
        account                        = local.account
        project                        = local.project
        application                    = local.application
        runtime                        = local.lambda_defaults.runtime
        timeout                        = local.lambda_defaults.timeout
        memory_size                    = local.lambda_defaults.memory_size
        layers                         = local.lambda_defaults.layers
        environment_variables          = local.lambda_defaults.environment_variables
        reserved_concurrent_executions = local.lambda_defaults.reserved_concurrent_executions
      },
      lambda,
      {
        # Computed full Lambda function name
        full_name = lower("${local.account}-${local.project}-${local.application}-${lambda.name}")
        # Computed role ARN
        role_arn = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:role/${lower("${local.account}-${local.project}-${local.application}-${lambda.role_name}")}"
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
              lambda_function_arn = "arn:aws:lambda:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:function:${local.lambdas_map[lambda_notif.lambda_name].full_name}"
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

  # Enrich IAM roles with computed values and trust policies
  iam_roles_enriched = [
    for role in local.iam_roles : merge(
      {
        account             = local.account
        project             = local.project
        application         = local.application
        managed_policy_arns = []
      },
      role,
      {
        # Computed full role name
        full_name = lower("${local.account}-${local.project}-${local.application}-${role.name}")
        # Computed assume role policy document
        assume_role_policy = jsonencode({
          Version = "2012-10-17"
          Statement = [
            {
              Effect = "Allow"
              Principal = {
                Service = role.assume_role_services
              }
              Action = "sts:AssumeRole"
            }
          ]
        })
        # Transform inline policies to policy documents
        inline_policies = [
          for policy in role.inline_policies : {
            name = policy.name
            policy = jsonencode({
              Version = "2012-10-17"
              Statement = [
                for statement in policy.policy_statements : {
                  Effect   = statement.effect
                  Action   = statement.actions
                  Resource = statement.resources
                }
              ]
            })
          }
        ]
      }
    )
  ]

  # Create a map of IAM roles keyed by name for easy lookup
  iam_roles_map = {
    for role in local.iam_roles_enriched : role.name => role
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
        # Resolved IAM role ARN
        role_arn = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:role/${local.iam_roles_map[crawler.iam_role_name].full_name}"
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

  # Enrich Step Functions state machine configurations
  state_machines_enriched = [
    for sm in local.state_machines : merge(
      sm,
      {
        account     = local.account
        project     = local.project
        application = local.application
        full_name   = lower("${local.account}-${local.project}-${local.application}-${sm.name}")
        role_arn    = local.iam_roles_map[sm.iam_role_name].full_name != "" ? "arn:aws:iam::${data.aws_caller_identity.current.account_id}:role/${lower("${local.account}-${local.project}-${local.application}-${sm.iam_role_name}")}" : ""
      }
    )
  ]

  # Create a map of state machines keyed by name
  state_machines_map = {
    for sm in local.state_machines_enriched : sm.name => sm
  }
}
