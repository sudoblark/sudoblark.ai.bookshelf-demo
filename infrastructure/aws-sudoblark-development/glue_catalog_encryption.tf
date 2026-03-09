# Retrieve AWS-managed Glue KMS key
data "aws_kms_key" "glue" {
  key_id = "alias/aws/glue"
}

# Enable Glue Data Catalog encryption at rest for security compliance
# CKV_AWS_195 - Glue Data Catalog encryption is required for data at rest protection
resource "aws_glue_data_catalog_encryption_settings" "catalog_encryption" {
  data_catalog_encryption_settings {
    # Encrypt connection passwords
    connection_password_encryption {
      return_connection_password_encrypted = true
      aws_kms_key_id                       = data.aws_kms_key.glue.arn
    }

    # Encrypt catalog metadata
    encryption_at_rest {
      catalog_encryption_mode = "SSE-KMS"
      sse_aws_kms_key_id      = data.aws_kms_key.glue.arn
    }
  }
}
