module "lambda_layer" {
  source = "../../modules/infrastructure/lambda-layer"
  layers = module.data.layers
}
