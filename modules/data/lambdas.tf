/*
  Lambda Functions data structure definition:

  Each lambda object requires:
  - name (string): The Lambda function identifier (will be prefixed with account-project-application)
  - zip_file_path (string): Path to the ZIP file containing the Lambda code
  - handler (string): The function entrypoint in your code (e.g., "index.handler")
  - role_name (string): Name of the IAM role (will be prefixed with account-project-application)

  Optional fields:
  - description (string): Description of the Lambda function (default: "")
  - runtime (string): Runtime environment (default: from lambda_defaults)
  - timeout (number): Execution timeout in seconds (default: from lambda_defaults)
  - memory_size (number): Memory in MB (default: from lambda_defaults)
  - layers (list(string)): Lambda layer ARNs (default: from lambda_defaults)
  - environment_variables (map(string)): Environment variables (default: from lambda_defaults)

  Constraints:
  - Lambda names must be unique within the configuration
  - Final function name will be: account-project-application-name (all lowercase)
  - ZIP file path must exist and be accessible
  - Role will be assumed to exist at: arn:aws:iam::{account_id}:role/account-project-application-role_name

  Example:
  {
    name             = "unzip-processor"
    description      = "Extracts ZIP files from landing to raw bucket"
    zip_file_path    = "./lambda-packages/unzip-processor.zip"
    handler          = "lambda_function.handler"
    runtime          = "python3.11"
    timeout          = 60
    memory_size      = 512
    role_name        = "unzip-processor-role"
    environment_variables = {
      RAW_BUCKET = "raw"
      LOG_LEVEL  = "INFO"
    }
  }
*/

locals {
  # Define Lambda functions
  lambdas = [
    {
      name          = "ops"
      description   = "Read-only ops dashboard endpoints: GET /ops/files and GET /ops/files/{file_id}"
      zip_file_path = "../../lambda-packages/ops.zip"
      handler       = "lambda_function.handler"
      runtime       = "python3.11"
      timeout       = 30
      memory_size   = 128
      layers = [
        # AWS Lambda Powertools for Python (eu-west-2, Python 3.11)
        # See: https://docs.powertools.aws.dev/lambda/python/latest/#lambda-layer
        "arn:aws:lambda:eu-west-2:017000801446:layer:AWSLambdaPowertoolsPythonV3-python311-x86_64:7"
      ]
      environment_variables = {
        TRACKING_TABLE = "${var.account}-${local.project}-${local.application}-ingestion-tracking"
        LOG_LEVEL      = "INFO"
      }
      iam_policy_statements = [
        {
          sid    = "IngestionTrackingRead"
          effect = "Allow"
          actions = [
            "dynamodb:GetItem",
            "dynamodb:Scan",
            "dynamodb:Query"
          ]
          resources = [
            "arn:aws:dynamodb:*:*:table/${var.account}-${local.project}-${local.application}-ingestion-tracking",
            "arn:aws:dynamodb:*:*:table/${var.account}-${local.project}-${local.application}-ingestion-tracking/index/*"
          ]
        }
      ]
    }
  ]
}
