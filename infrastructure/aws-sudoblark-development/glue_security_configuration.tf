# Glue Security Configuration for encryption compliance
# CKV_AWS_195 - Glue components must have security configuration
# Using SSE-S3 to avoid KMS costs
resource "aws_glue_security_configuration" "default" {
  name = "${var.account}-glue-security-config"

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
