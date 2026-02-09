# Terraform configuration
terraform {
  required_version = "~> 1.14"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 6.0"
    }
  }

  backend "s3" {
    bucket  = "aws-sudoblark-development-terraform-state"
    key     = "aws/aws-sudoblark-development/sudoblark.ai.bookshelf-demo/terraform.tfstate"
    encrypt = true
    region  = "eu-west-2"
    assume_role = {
      role_arn     = "arn:aws:iam::796012663443:role/aws-sudoblark-development-github-cicd-role"
      session_name = "sudoblark.ai.bookshelf-demo"
      external_id  = "CI_CD_PLATFORM"
    }
  }
}

provider "aws" {
  region = "eu-west-2"

  assume_role {
    role_arn     = "arn:aws:iam::796012663443:role/aws-sudoblark-development-github-cicd-role"
    session_name = "sudoblark.ai.bookshelf-demo"
    external_id  = "CI_CD_PLATFORM"
  }

  default_tags {
    tags = {
      environment = "development"
      managed_by  = "sudoblark.ai.bookshelf-demo"
      project     = "bookshelf-demo"
    }
  }
}
