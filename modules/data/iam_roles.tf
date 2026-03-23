/*
  IAM roles are no longer defined in the data layer.

  IAM roles and policies are now owned by the infrastructure modules that need them:
  - Lambda IAM roles     → modules/infrastructure/lambda (created from iam_policy_statements in lambdas.tf)
  - Glue crawler roles   → modules/infrastructure/glue   (created from iam_policy_statements in glue_crawlers.tf)

  Each lambda/crawler definition carries its own iam_policy_statements list.
  The infrastructure module builds the role, attaches AWSLambdaBasicExecutionRole /
  AWSGlueServiceRole, and creates an inline policy from those statements.
*/
