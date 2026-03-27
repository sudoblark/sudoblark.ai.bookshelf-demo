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
  # Define Lambda functions for the ETL pipeline
  lambdas = [
    {
      name          = "landing-to-raw"
      description   = "AV scans files in landing and promotes clean files to raw, triggering the enrichment state machine"
      zip_file_path = "../../lambda-packages/landing-to-raw.zip"
      handler       = "lambda_function.handler"
      runtime       = "python3.11"
      timeout       = 60
      memory_size   = 512
      environment_variables = {
        DATA_LAKE_PREFIX  = "${var.account}-${local.project}-${local.application}"
        TRACKING_TABLE    = "${var.account}-${local.project}-${local.application}-ingestion-tracking"
        STATE_MACHINE_ARN = "arn:aws:states:eu-west-2:PLACEHOLDER:stateMachine:PLACEHOLDER-bookshelf-demo-raw-to-enriched"
        LOG_LEVEL         = "INFO"
      }
      iam_policy_statements = [
        {
          sid       = "LandingBucketRead"
          effect    = "Allow"
          actions   = ["s3:GetObject"]
          resources = ["arn:aws:s3:::${var.account}-${local.project}-${local.application}-landing/*"]
        },
        {
          sid       = "LandingBucketDelete"
          effect    = "Allow"
          actions   = ["s3:DeleteObject"]
          resources = ["arn:aws:s3:::${var.account}-${local.project}-${local.application}-landing/*"]
        },
        {
          sid       = "RawBucketWrite"
          effect    = "Allow"
          actions   = ["s3:PutObject"]
          resources = ["arn:aws:s3:::${var.account}-${local.project}-${local.application}-raw/*"]
        },
        {
          sid       = "IngestionTrackingWrite"
          effect    = "Allow"
          actions   = ["dynamodb:PutItem", "dynamodb:UpdateItem", "dynamodb:GetItem"]
          resources = ["arn:aws:dynamodb:*:*:table/${var.account}-${local.project}-${local.application}-ingestion-tracking"]
        },
        {
          sid       = "StartExecution"
          effect    = "Allow"
          actions   = ["states:StartExecution"]
          resources = ["arn:aws:states:*:*:stateMachine:*-bookshelf-demo-raw-to-enriched"]
        }
      ]
    },
    {
      name          = "metadata-extractor"
      description   = "Extracts book metadata from images using Bedrock and writes to Parquet format"
      zip_file_path = "../../lambda-packages/metadata-extractor.zip"
      handler       = "lambda_function.handler"
      runtime       = "python3.11"
      timeout       = 300 # 5 minutes for LLM processing
      memory_size   = 1024
      layer_names   = ["bookshelf-agent"]
      layers = [
        # AWS Lambda Powertools for Python (eu-west-2, Python 3.11)
        # See: https://docs.powertools.aws.dev/lambda/python/latest/#lambda-layer
        "arn:aws:lambda:eu-west-2:017000801446:layer:AWSLambdaPowertoolsPythonV3-python311-x86_64:7"
      ]
      environment_variables = {
        DATA_LAKE_PREFIX = "${var.account}-${local.project}-${local.application}"
        TRACKING_TABLE   = "${var.account}-${local.project}-${local.application}-ingestion-tracking"
        LOG_LEVEL        = "INFO"
        BEDROCK_MODEL_ID = "anthropic.claude-3-haiku-20240307-v1:0"
      }
      iam_policy_statements = [
        {
          sid       = "RawBucketRead"
          effect    = "Allow"
          actions   = ["s3:GetObject"]
          resources = ["arn:aws:s3:::${var.account}-${local.project}-${local.application}-raw/*"]
        },
        {
          sid       = "ProcessedBucketWrite"
          effect    = "Allow"
          actions   = ["s3:PutObject"]
          resources = ["arn:aws:s3:::${var.account}-${local.project}-${local.application}-processed/*"]
        },
        {
          sid       = "BedrockInvokeModel"
          effect    = "Allow"
          actions   = ["bedrock:InvokeModel"]
          resources = ["arn:aws:bedrock:eu-west-2::foundation-model/anthropic.claude-3-haiku-20240307-v1:0"]
        },
        {
          sid       = "IngestionTrackingWrite"
          effect    = "Allow"
          actions   = ["dynamodb:PutItem", "dynamodb:UpdateItem", "dynamodb:GetItem"]
          resources = ["arn:aws:dynamodb:*:*:table/${var.account}-${local.project}-${local.application}-ingestion-tracking"]
        }
      ]
    }
  ]
}
