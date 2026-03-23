resource "aws_s3_bucket" "bucket" {
  for_each = { for bucket in var.buckets : bucket.name => bucket }

  bucket        = each.value.full_name
  force_destroy = true

  tags = {
    Name = each.value.full_name
  }
}

resource "aws_s3_bucket_public_access_block" "bucket" {
  for_each = { for bucket in var.buckets : bucket.name => bucket }

  bucket = aws_s3_bucket.bucket[each.key].id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_object" "folder" {
  for_each = merge([
    for bucket in var.buckets : {
      for folder in bucket.folder_paths :
      "${bucket.name}/${folder}" => {
        bucket_key = bucket.name
        folder     = folder
      }
    }
  ]...)

  bucket = aws_s3_bucket.bucket[each.value.bucket_key].id
  key    = "${each.value.folder}/"
  source = "/dev/null"
}
