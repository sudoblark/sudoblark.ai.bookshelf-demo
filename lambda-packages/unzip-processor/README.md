# Unzip Processor Lambda Function

Extracts image files from ZIP archives uploaded to the landing S3 bucket.

## Functionality

- Triggered by S3 ObjectCreated events on ZIP files in the landing bucket
- Extracts only image files (jpg, jpeg, png, gif, bmp, tiff, webp)
- Uploads extracted images to the raw bucket
- Handles path traversal prevention
- Comprehensive error logging

## Environment Variables

- `RAW_BUCKET`: Short name of the raw bucket (e.g., "raw")
- `LOG_LEVEL`: Logging level (default: "INFO")

## Dependencies

- aws-lambda-powertools: For structured event parsing
- boto3: AWS SDK for S3 operations

## Testing

Package and test locally:
```bash
cd lambda-packages/unzip-processor
pip install -r requirements.txt -t .
zip -r ../unzip-processor.zip .
```
