locals {
  layers_map = { for layer in var.layers : layer.name => layer }
}

resource "aws_lambda_layer_version" "layer" {
  for_each = local.layers_map

  layer_name          = each.value.full_name
  description         = each.value.description
  filename            = each.value.zip_file_path
  source_code_hash    = filebase64sha256(each.value.zip_file_path)
  compatible_runtimes = each.value.compatible_runtimes
}
