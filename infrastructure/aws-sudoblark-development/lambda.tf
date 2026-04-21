locals {
  # Resolve layer_names to ARNs at the deployment layer, where runtime ARNs are available.
  # The data module declares layer_names by short name; here we look them up and merge into layers.
  lambdas_with_resolved_layers = [
    for lambda in module.data.lambdas : merge(lambda, {
      layers = concat(
        lambda.layers,
        [for name in lambda.layer_names : module.lambda_layer.layer_arns[name]]
      )
    })
  ]
}

module "lambda" {
  source  = "../../modules/infrastructure/lambda"
  lambdas = local.lambdas_with_resolved_layers
}
