# Metadata Extractor Lambda Function

Extracts book metadata from images using AWS Bedrock (Claude 3 Haiku) and writes results to Parquet format.

## Functionality

- Triggered by S3 ObjectCreated events on image files in the raw bucket
- Downloads images from S3
- Resizes images for Bedrock API efficiency
- Uses Claude 3 Haiku vision model to extract book metadata
- Writes structured metadata to Parquet files in processed bucket
- Comprehensive error handling and logging

## Environment Variables

- `PROCESSED_BUCKET`: Short name of the processed bucket (e.g., "processed")
- `LOG_LEVEL`: Logging level (default: "INFO")
- `BEDROCK_MODEL_ID`: Bedrock model ID (default: "anthropic.claude-3-haiku-20240307-v1:0")
- `AWS_REGION`: AWS region for Bedrock (default: "eu-west-2")

## Metadata Fields

Extracted metadata includes:
- `id`: Unique identifier (UUID)
- `filename`: Original filename
- `title`: Book title
- `author`: Author name
- `isbn`: ISBN (digits only)
- `publisher`: Publisher name
- `published_year`: Publication year (integer or null)
- `description`: Brief description
- `processed_at`: ISO 8601 timestamp

## Lambda Layers

This function requires the AWS SDK for pandas Lambda layer:
- **AWS SDK for pandas** (Python 3.11): Provides pandas and pyarrow
  - ARN: `arn:aws:lambda:eu-west-2:336392948345:layer:AWSSDKPandas-Python311:11`

Pillow is bundled directly in the deployment package for reliability.

## IAM Permissions

Requires permissions for:
- `s3:GetObject` on raw bucket
- `s3:PutObject` on processed bucket
- `bedrock:InvokeModel` for Claude 3 Haiku

## Testing

Package and test locally:
```bash
cd lambda-packages/metadata-extractor
pip install -r requirements.txt -t .
zip -r ../metadata-extractor.zip .
```

Note: When testing locally, you'll need to install pandas, pyarrow, and Pillow. In production, these are provided by Lambda layers.
