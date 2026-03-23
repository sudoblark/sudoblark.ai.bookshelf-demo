locals {
  crawlers_map = { for crawler in var.crawlers : crawler.name => crawler }
}

data "aws_iam_policy_document" "glue_assume_role" {
  for_each = local.crawlers_map

  statement {
    effect = "Allow"
    principals {
      type        = "Service"
      identifiers = ["glue.amazonaws.com"]
    }
    actions = ["sts:AssumeRole"]
  }
}

resource "aws_iam_role" "crawler" {
  for_each = local.crawlers_map

  name               = each.value.role_name
  assume_role_policy = data.aws_iam_policy_document.glue_assume_role[each.key].json

  tags = {
    Name = each.value.role_name
  }
}

resource "aws_iam_role_policy_attachment" "glue_service" {
  for_each = local.crawlers_map

  role       = aws_iam_role.crawler[each.key].name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSGlueServiceRole"
}

data "aws_iam_policy_document" "crawler_policy" {
  for_each = local.crawlers_map

  dynamic "statement" {
    for_each = each.value.iam_policy_statements

    content {
      sid       = statement.value.sid
      effect    = statement.value.effect
      actions   = statement.value.actions
      resources = statement.value.resources
    }
  }
}

resource "aws_iam_role_policy" "crawler_policy" {
  for_each = local.crawlers_map

  name   = "${each.value.name}-policy"
  role   = aws_iam_role.crawler[each.key].id
  policy = data.aws_iam_policy_document.crawler_policy[each.key].json
}

resource "aws_glue_crawler" "crawler" {
  for_each = local.crawlers_map

  name                   = each.value.full_name
  database_name          = each.value.database_full_name
  description            = each.value.description
  role                   = aws_iam_role.crawler[each.key].arn
  schedule               = each.value.schedule != "" ? each.value.schedule : null
  table_prefix           = each.value.table_prefix != "" ? each.value.table_prefix : null
  security_configuration = aws_glue_security_configuration.default.name

  s3_target {
    path = each.value.s3_target_full_path
  }

  depends_on = [
    aws_iam_role.crawler,
    aws_iam_role_policy.crawler_policy,
    aws_glue_catalog_database.database,
    aws_glue_security_configuration.default,
  ]
}
