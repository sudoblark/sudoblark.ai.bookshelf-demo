module "lambda" {
  source     = "../../modules/infrastructure/lambda"
  lambdas    = module.data.lambdas
  layer_arns = module.lambda_layer.layer_arns

  depends_on = [module.lambda_layer]
}
