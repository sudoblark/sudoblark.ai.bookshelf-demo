# Create all S3 buckets defined in the data module
resource "aws_s3_bucket" "bucket" {
  for_each = { for bucket in module.data.buckets : bucket.name => bucket }

  bucket = each.value.full_name

  tags = {
    Name = each.value.full_name
  }
}

resource "aws_s3_bucket_public_access_block" "bucket" {
  for_each = { for bucket in module.data.buckets : bucket.name => bucket }

  bucket = aws_s3_bucket.bucket[each.key].id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_object" "folder" {
  for_each = merge([
    for bucket in module.data.buckets : {
      for folder in bucket.folder_paths :
      "${bucket.name}/${folder}" => {
        bucket_id = bucket.name
        folder    = folder
      }
    }
  ]...)

  bucket = aws_s3_bucket.bucket[each.value.bucket_id].id
  key    = "${each.value.folder}/"
  source = "/dev/null"
}
