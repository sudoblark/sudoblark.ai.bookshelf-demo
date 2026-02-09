# Create all Glue databases defined in the data module
resource "aws_glue_catalog_database" "database" {
  for_each = { for db in module.data.glue_databases : db.name => db }

  name        = each.value.full_name
  description = each.value.description
}
