module "step_functions" {
  source         = "../../modules/infrastructure/step_functions"
  state_machines = module.data.step_functions

  depends_on = [module.lambda]
}
