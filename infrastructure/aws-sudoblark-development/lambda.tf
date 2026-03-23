module "lambda" {
  source  = "../../modules/infrastructure/lambda"
  lambdas = module.data.lambdas
}
