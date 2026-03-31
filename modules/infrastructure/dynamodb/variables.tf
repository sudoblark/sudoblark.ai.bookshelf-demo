variable "dynamodb_tables" {
  description = "Enriched list of DynamoDB tables to create"
  type = list(object({
    name         = string
    full_name    = string
    hash_key     = string
    range_key    = optional(string)
    billing_mode = string
    attributes = list(object({
      name = string
      type = string
    }))
    global_secondary_indexes = list(object({
      name            = string
      hash_key        = string
      range_key       = string
      projection_type = string
    }))
  }))
}
