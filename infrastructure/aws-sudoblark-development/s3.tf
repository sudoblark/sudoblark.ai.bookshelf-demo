module "s3" {
  source  = "../../modules/infrastructure/s3"
  buckets = module.data.buckets
}
