module "dynamodb" {
  source          = "../../modules/infrastructure/dynamodb"
  dynamodb_tables = module.data.dynamodb_tables
}
