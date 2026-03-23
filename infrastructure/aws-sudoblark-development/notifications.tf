module "notifications" {
  source        = "../../modules/infrastructure/notifications"
  notifications = module.data.notifications
  bucket_ids    = module.s3.bucket_ids
  bucket_arns   = module.s3.bucket_arns

  depends_on = [module.s3, module.lambda]
}
