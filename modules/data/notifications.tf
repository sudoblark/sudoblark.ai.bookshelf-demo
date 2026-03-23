/*
  S3 Bucket Notifications data structure definition:

  Each notification object requires:
  - bucket_name (string): Name of the bucket to attach notifications to (must match a bucket.name)
  - lambda_notifications (list(object)): List of Lambda notification configurations

  Each lambda_notification object requires:
  - lambda_name (string): Name of the Lambda function (must match a lambda.name)

  Optional fields per lambda_notification:
  - events (list(string)): S3 events to trigger on (default: from notification_defaults)
  - filter_prefix (string): Object key prefix filter (default: "")
  - filter_suffix (string): Object key suffix filter (default: "")

  Constraints:
  - bucket_name must reference an existing bucket defined in buckets.tf
  - lambda_name must reference an existing Lambda defined in lambdas.tf
  - Common S3 events: "s3:ObjectCreated:*", "s3:ObjectCreated:Put", "s3:ObjectRemoved:*"
  - Lambda must have appropriate permissions to be invoked by S3

  Example:
  {
    bucket_name = "landing"
    lambda_notifications = [
      {
        lambda_name   = "unzip-processor"
        events        = ["s3:ObjectCreated:*"]
        filter_prefix = ""
        filter_suffix = ".zip"
      }
    ]
  }
*/

locals {
  # Define S3 bucket notifications to trigger Lambda functions
  notifications = [
    {
      bucket_name = "landing"
      lambda_notifications = [
        {
          lambda_name   = "av-scanner"
          events        = ["s3:ObjectCreated:*"]
          filter_prefix = ""
          filter_suffix = ""
        }
      ]
    },
    {
      bucket_name = "raw"
      lambda_notifications = [
        {
          lambda_name   = "metadata-extractor"
          events        = ["s3:ObjectCreated:*"]
          filter_prefix = ""
          filter_suffix = "" # Process all image files (jpg, jpeg, png, etc.)
        }
      ]
    }
  ]
}
