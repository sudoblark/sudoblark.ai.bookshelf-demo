variable "state_machines" {
  description = "Enriched list of Step Functions state machines to create"
  type = list(object({
    name        = string
    full_name   = string
    role_name   = string
    description = string
    definition  = string
    iam_policy_statements = list(object({
      sid       = string
      effect    = string
      actions   = list(string)
      resources = list(string)
    }))
  }))
}
