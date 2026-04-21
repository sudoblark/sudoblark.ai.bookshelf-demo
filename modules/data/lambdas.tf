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
      name          = "raw-to-processed-copy"
      description   = "Copies accepted metadata JSON from raw bucket to processed bucket"
      zip_file_path = "./lambda-packages/raw-to-processed-copy.zip"
      handler       = "lambda_function.handler"
      timeout       = 30
      memory_size   = 256
      environment_variables = {
        TRACKING_TABLE   = lower("${var.account}-${var.project}-${var.application}-ingestion-tracking")
        RAW_BUCKET       = lower("${var.account}-${var.project}-${var.application}-raw")
        PROCESSED_BUCKET = lower("${var.account}-${var.project}-${var.application}-processed")
        LOG_LEVEL        = "INFO"
      }
      iam_policy_statements = [
        {
          sid     = "S3ReadRaw"
          effect  = "Allow"
          actions = ["s3:GetObject"]
          resources = [
            "arn:aws:s3:::${lower("${var.account}-${var.project}-${var.application}-raw")}/*"
          ]
        },
        {
          sid     = "S3WriteProcessed"
          effect  = "Allow"
          actions = ["s3:PutObject"]
          resources = [
            "arn:aws:s3:::${lower("${var.account}-${var.project}-${var.application}-processed")}/*"
          ]
        },
        {
          sid    = "DynamoDBTracking"
          effect = "Allow"
          actions = [
            "dynamodb:GetItem",
            "dynamodb:UpdateItem",
          ]
          resources = [
            "arn:aws:dynamodb:*:*:table/${lower("${var.account}-${var.project}-${var.application}-ingestion-tracking")}"
          ]
        },
      ]
    },
    {
      name          = "vector-generator"
      description   = "Generates Bedrock Titan text embeddings for processed book metadata"
      zip_file_path = "./lambda-packages/vector-generator.zip"
      handler       = "lambda_function.handler"
      timeout       = 60
      memory_size   = 512
      environment_variables = {
        TRACKING_TABLE     = lower("${var.account}-${var.project}-${var.application}-ingestion-tracking")
        PROCESSED_BUCKET   = lower("${var.account}-${var.project}-${var.application}-processed")
        EMBEDDING_MODEL_ID = "amazon.titan-embed-text-v1"
        BEDROCK_REGION     = "us-east-1"
        LOG_LEVEL          = "INFO"
      }
      iam_policy_statements = [
        {
          sid     = "BedrockInvokeModel"
          effect  = "Allow"
          actions = ["bedrock:InvokeModel"]
          resources = [
            "arn:aws:bedrock:us-east-1::foundation-model/amazon.titan-embed-text-v1"
          ]
        },
        {
          sid     = "S3ReadWriteProcessed"
          effect  = "Allow"
          actions = ["s3:GetObject", "s3:PutObject"]
          resources = [
            "arn:aws:s3:::${lower("${var.account}-${var.project}-${var.application}-processed")}/*"
          ]
        },
        {
          sid    = "DynamoDBTracking"
          effect = "Allow"
          actions = [
            "dynamodb:GetItem",
            "dynamodb:UpdateItem",
          ]
          resources = [
            "arn:aws:dynamodb:*:*:table/${lower("${var.account}-${var.project}-${var.application}-ingestion-tracking")}"
          ]
        },
      ]
    },
  ]
}
