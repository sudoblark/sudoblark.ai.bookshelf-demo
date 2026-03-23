resource "aws_glue_catalog_database" "database" {
  for_each = { for db in var.databases : db.name => db }

  name        = each.value.full_name
  description = each.value.description
}
