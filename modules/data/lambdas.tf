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
      name          = "unzip-processor"
      description   = "Extracts image files from ZIP archives in landing bucket to raw bucket"
      zip_file_path = "../../lambda-packages/unzip-processor.zip"
      handler       = "lambda_function.handler"
      runtime       = "python3.11"
      timeout       = 60
      memory_size   = 512
      role_name     = "unzip-processor-role"
      environment_variables = {
        RAW_BUCKET = "raw"
        LOG_LEVEL  = "INFO"
      }
    },
    {
      name          = "metadata-extractor"
      description   = "Extracts book metadata from images using Bedrock and writes to Parquet format"
      zip_file_path = "../../lambda-packages/metadata-extractor.zip"
      handler       = "lambda_function.handler"
      runtime       = "python3.11"
      timeout       = 300 # 5 minutes for LLM processing
      memory_size   = 1024
      role_name     = "metadata-extractor-role"
      layers = [
        # AWS SDK for pandas (includes pandas, pyarrow, numpy, etc.)
        # Version 11 for Python 3.11 in eu-west-2
        # See: https://aws-sdk-pandas.readthedocs.io/en/stable/layers.html
        "arn:aws:lambda:eu-west-2:336392948345:layer:AWSSDKPandas-Python311:11",
        # Pillow layer for image processing
        # ARN for eu-west-2 Python 3.11
        "arn:aws:lambda:eu-west-2:770693421928:layer:Klayers-p311-pillow:10"
      ]
      environment_variables = {
        PROCESSED_BUCKET = "processed"
        LOG_LEVEL        = "INFO"
        AWS_REGION       = "eu-west-2"
        BEDROCK_MODEL_ID = "anthropic.claude-3-haiku-20240307-v1:0"
      }
    }
  ]
}
