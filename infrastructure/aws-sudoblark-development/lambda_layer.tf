module "lambda_layer" {
  source           = "../../modules/infrastructure/lambda-layer"
  layers           = module.data.layers
  artifacts_bucket = module.s3.bucket_ids["artifacts"]

  depends_on = [module.s3]
}
