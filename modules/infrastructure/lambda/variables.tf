variable "lambdas" {
  description = "Enriched list of Lambda functions to create"
  type = list(object({
    name                  = string
    full_name             = string
    role_name             = string
    description           = string
    zip_file_path         = string
    handler               = string
    runtime               = string
    timeout               = number
    memory_size           = number
    layers                = list(string)
    layer_names           = optional(list(string), [])
    environment_variables = map(string)
    iam_policy_statements = list(object({
      sid       = string
      effect    = string
      actions   = list(string)
      resources = list(string)
    }))
  }))
}

variable "layer_arns" {
  description = "Map of layer short name to ARN, used to resolve layer_names on Lambda functions"
  type        = map(string)
  default     = {}
}
