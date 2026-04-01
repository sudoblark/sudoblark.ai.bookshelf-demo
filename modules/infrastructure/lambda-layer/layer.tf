locals {
  layers_map = { for layer in var.layers : layer.name => layer }
}

resource "aws_s3_object" "layer_zip" {
  for_each = local.layers_map

  bucket = var.artifacts_bucket
  key    = "layers/${each.key}.zip"
  source = each.value.zip_file_path
  etag   = filemd5(each.value.zip_file_path)
}

resource "aws_lambda_layer_version" "layer" {
  for_each = local.layers_map

  layer_name          = each.value.full_name
  description         = each.value.description
  s3_bucket           = var.artifacts_bucket
  s3_key              = aws_s3_object.layer_zip[each.key].key
  source_code_hash    = filebase64sha256(each.value.zip_file_path)
  compatible_runtimes = each.value.compatible_runtimes

  depends_on = [aws_s3_object.layer_zip]
}
