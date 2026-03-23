variable "account" {
  description = "AWS account name (e.g. aws-sudoblark-development)"
  type        = string
}

variable "project" {
  description = "Project name (e.g. bookshelf)"
  type        = string
}

variable "application" {
  description = "Application name (e.g. demo)"
  type        = string
}

variable "environment" {
  description = "Deployment environment (development, staging, production)"
  type        = string
}
