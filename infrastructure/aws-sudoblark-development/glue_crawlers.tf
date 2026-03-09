# Create all Glue crawlers defined in the data module
resource "aws_glue_crawler" "crawler" {
  for_each = { for crawler in module.data.glue_crawlers : crawler.name => crawler }

  name                   = each.value.full_name
  database_name          = each.value.database_full_name
  description            = each.value.description
  role                   = each.value.role_arn
  schedule               = each.value.schedule != "" ? each.value.schedule : null
  table_prefix           = each.value.table_prefix != "" ? each.value.table_prefix : null
  security_configuration = aws_glue_security_configuration.default.name

  s3_target {
    path = each.value.s3_target_full_path
  }

  # Ensure IAM role and Glue database exist before creating crawler
  depends_on = [
    aws_iam_role.role,
    aws_glue_catalog_database.database,
    aws_glue_security_configuration.default
  ]
}
