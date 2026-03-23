# Instantiate the data module to get all infrastructure definitions
module "data" {
  source = "../../modules/data"

  account     = var.account
  project     = var.project
  application = var.application
  environment = var.environment
}
