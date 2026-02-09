# Create all Lambda functions defined in the data module
resource "aws_lambda_function" "lambda" {
  for_each = { for lambda in module.data.lambdas : lambda.name => lambda }

  function_name = each.value.full_name
  description   = each.value.description
  role          = each.value.role_arn
  handler       = each.value.handler
  runtime       = each.value.runtime
  timeout       = each.value.timeout
  memory_size   = each.value.memory_size
  layers        = each.value.layers

  filename         = each.value.zip_file_path
  source_code_hash = filebase64sha256(each.value.zip_file_path)

  environment {
    variables = each.value.environment_variables
  }

  tags = {
    Name = each.value.full_name
  }

  # Ensure IAM roles exist before creating Lambda functions
  depends_on = [
    aws_iam_role.role,
    aws_iam_role_policy.inline_policy,
    aws_iam_role_policy_attachment.managed_policy
  ]
}
