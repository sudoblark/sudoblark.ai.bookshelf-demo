module "athena" {
  source     = "../../modules/infrastructure/athena"
  workgroups = module.data.athena_workgroups

  depends_on = [module.s3]
}
