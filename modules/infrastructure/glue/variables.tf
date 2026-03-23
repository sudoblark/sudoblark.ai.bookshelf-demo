variable "databases" {
  description = "Enriched list of Glue catalog databases to create"
  type = list(object({
    name        = string
    full_name   = string
    description = string
  }))
}

variable "crawlers" {
  description = "Enriched list of Glue crawlers to create"
  type = list(object({
    name                = string
    full_name           = string
    role_name           = string
    description         = string
    database_full_name  = string
    s3_target_full_path = string
    schedule            = string
    table_prefix        = string
    iam_policy_statements = list(object({
      sid       = string
      effect    = string
      actions   = list(string)
      resources = list(string)
    }))
  }))
}

variable "security_config_name" {
  description = "Name for the Glue security configuration (from data module)"
  type        = string
}
