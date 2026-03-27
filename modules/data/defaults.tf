# S3 key convention (all tiers):
#   {user_id}/{upload_id}/{filename}
#
# user_id   = Cognito user sub (UUID)
# upload_id = UUID generated at upload time by the pre-signed URL Lambda
# filename  = Original source filename
#
# ZIPs land at:  landing/uploads/{user_id}/{upload_id}/{archive}.zip
# Images land at: landing/uploads/{user_id}/{upload_id}/{filename}
# Raw objects:   raw/{user_id}/{upload_id}/{filename}
# Parquet:       processed/{user_id}/{upload_id}/{filename}.parquet

locals {
  # Resolved from input variables — promotes environment parity across dev/staging/prod
  account     = var.account
  project     = var.project
  application = var.application
  environment = var.environment

  # Default Lambda configurations
  lambda_defaults = {
    runtime               = "python3.11"
    timeout               = 30
    memory_size           = 256
    layers                = []
    layer_names           = []
    environment_variables = {}
  }

  # Default Lambda Layer configurations
  layer_defaults = {
    description         = ""
    compatible_runtimes = ["python3.11"]
  }

  # Default S3 bucket configurations
  # (glue_security_config_name is computed in infrastructure.tf once local.account is available)

  s3_defaults = {
    folder_paths = []
  }

  # Default notification configurations
  notification_defaults = {
    events = ["s3:ObjectCreated:*"]
  }
}
