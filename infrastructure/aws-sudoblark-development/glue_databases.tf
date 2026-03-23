module "glue" {
  source               = "../../modules/infrastructure/glue"
  databases            = module.data.glue_databases
  crawlers             = module.data.glue_crawlers
  security_config_name = module.data.glue_security_config_name

  depends_on = [module.s3]
}
