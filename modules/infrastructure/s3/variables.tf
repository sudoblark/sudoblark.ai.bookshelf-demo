variable "buckets" {
  description = "Enriched list of S3 buckets to create"
  type = list(object({
    name         = string
    full_name    = string
    folder_paths = list(string)
  }))
}
