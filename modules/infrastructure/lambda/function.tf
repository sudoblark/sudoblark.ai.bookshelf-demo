locals {
  lambdas_map = { for lambda in var.lambdas : lambda.name => lambda }

  # Merge public layer ARNs (layers) with locally-managed layer ARNs (resolved from layer_names)
  resolved_layers = {
    for name, lambda in local.lambdas_map :
    name => concat(
      lambda.layers,
      [for layer_name in lambda.layer_names : var.layer_arns[layer_name]]
    )
  }
}

data "aws_iam_policy_document" "assume_role" {
  for_each = local.lambdas_map

  statement {
    effect = "Allow"
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
    actions = ["sts:AssumeRole"]
  }
}

resource "aws_iam_role" "lambda" {
  for_each = local.lambdas_map

  name               = each.value.role_name
  assume_role_policy = data.aws_iam_policy_document.assume_role[each.key].json

  tags = {
    Name = each.value.role_name
  }
}

resource "aws_iam_role_policy_attachment" "basic_execution" {
  for_each = local.lambdas_map

  role       = aws_iam_role.lambda[each.key].name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

data "aws_iam_policy_document" "lambda_policy" {
  for_each = local.lambdas_map

  dynamic "statement" {
    for_each = each.value.iam_policy_statements

    content {
      sid       = statement.value.sid
      effect    = statement.value.effect
      actions   = statement.value.actions
      resources = statement.value.resources
    }
  }
}

resource "aws_iam_role_policy" "lambda_policy" {
  for_each = local.lambdas_map

  name   = "${each.value.name}-policy"
  role   = aws_iam_role.lambda[each.key].id
  policy = data.aws_iam_policy_document.lambda_policy[each.key].json
}

resource "aws_cloudwatch_log_group" "lambda" {
  for_each = local.lambdas_map

  name              = "/aws/lambda/${each.value.full_name}"
  retention_in_days = 365
}

resource "aws_lambda_function" "function" {
  for_each = local.lambdas_map

  function_name = each.value.full_name
  description   = each.value.description
  role          = aws_iam_role.lambda[each.key].arn
  handler       = each.value.handler
  runtime       = each.value.runtime
  timeout       = each.value.timeout
  memory_size   = each.value.memory_size
  layers        = local.resolved_layers[each.key]

  filename         = each.value.zip_file_path
  source_code_hash = filebase64sha256(each.value.zip_file_path)

  environment {
    variables = each.value.environment_variables
  }

  tags = {
    Name = each.value.full_name
  }

  depends_on = [
    aws_iam_role.lambda,
    aws_iam_role_policy.lambda_policy,
    aws_cloudwatch_log_group.lambda,
  ]
}
