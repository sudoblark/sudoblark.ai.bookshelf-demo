locals {
  tables_map = { for table in var.dynamodb_tables : table.name => table }
}

resource "aws_dynamodb_table" "table" {
  for_each = local.tables_map

  name         = each.value.full_name
  billing_mode = each.value.billing_mode

  dynamic "key_schema" {
    for_each = concat(
      [{ attribute_name = each.value.hash_key, key_type = "HASH" }],
      each.value.range_key != null ? [{ attribute_name = each.value.range_key, key_type = "RANGE" }] : []
    )
    content {
      attribute_name = key_schema.value.attribute_name
      key_type       = key_schema.value.key_type
    }
  }

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
      projection_type = global_secondary_index.value.projection_type

      dynamic "key_schema" {
        for_each = concat(
          [{ attribute_name = global_secondary_index.value.hash_key, key_type = "HASH" }],
          global_secondary_index.value.range_key != null ? [{ attribute_name = global_secondary_index.value.range_key, key_type = "RANGE" }] : []
        )
        content {
          attribute_name = key_schema.value.attribute_name
          key_type       = key_schema.value.key_type
        }
      }
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
