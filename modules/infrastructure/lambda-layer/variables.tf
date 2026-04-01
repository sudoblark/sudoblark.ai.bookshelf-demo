variable "artifacts_bucket" {
  description = "S3 bucket ID to store Lambda layer zip packages before publishing"
  type        = string
}

variable "layers" {
  description = "Enriched list of Lambda layers to create"
  type = list(object({
    name                = string
    full_name           = string
    description         = string
    zip_file_path       = string
    compatible_runtimes = list(string)
  }))
}
