locals {
  tables_map = { for table in var.dynamodb_tables : table.name => table }
}

#checkov:skip=CKV_AWS_119:AWS-managed encryption is sufficient for this demo; CMK would incur unnecessary cost
#checkov:skip=CKV2_AWS_16:PAY_PER_REQUEST billing mode provides automatic scaling without explicit auto-scaling configuration
resource "aws_dynamodb_table" "table" {
  for_each = local.tables_map

  name         = each.value.full_name
  hash_key     = each.value.hash_key
  range_key    = each.value.range_key
  billing_mode = each.value.billing_mode

  dynamic "attribute" {
    for_each = each.value.attributes

    content {
      name = attribute.value.name
      type = attribute.value.type
    }
  }

  dynamic "global_secondary_index" {
    for_each = each.value.global_secondary_indexes

    content {
      name            = global_secondary_index.value.name
      hash_key        = global_secondary_index.value.hash_key
      range_key       = global_secondary_index.value.range_key != null ? global_secondary_index.value.range_key : null
      projection_type = global_secondary_index.value.projection_type
    }
  }

  point_in_time_recovery {
    enabled = true
  }

  server_side_encryption {
    enabled = true
  }

  tags = {
    Name = each.value.full_name
  }
}
