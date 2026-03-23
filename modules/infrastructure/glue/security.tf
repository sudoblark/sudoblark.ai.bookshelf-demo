# Retrieve AWS-managed Glue KMS key for catalog encryption
data "aws_kms_key" "glue" {
  key_id = "alias/aws/glue"
}

# Glue Security Configuration for encryption compliance
# CKV_AWS_195 - Glue components must have security configuration
# Using SSE-S3 to avoid KMS costs for job output; catalog uses SSE-KMS below
resource "aws_glue_security_configuration" "default" {
  name = var.security_config_name

  encryption_configuration {
    cloudwatch_encryption {
      cloudwatch_encryption_mode = "DISABLED"
    }

    job_bookmarks_encryption {
      job_bookmarks_encryption_mode = "DISABLED"
    }

    s3_encryption {
      s3_encryption_mode = "SSE-S3"
    }
  }
}

# Enable Glue Data Catalog encryption at rest
# CKV_AWS_195 - Glue Data Catalog encryption required for data at rest protection
resource "aws_glue_data_catalog_encryption_settings" "catalog_encryption" {
  data_catalog_encryption_settings {
    connection_password_encryption {
      return_connection_password_encrypted = true
      aws_kms_key_id                       = data.aws_kms_key.glue.arn
    }

    encryption_at_rest {
      catalog_encryption_mode = "SSE-KMS"
      sse_aws_kms_key_id      = data.aws_kms_key.glue.arn
    }
  }
}
