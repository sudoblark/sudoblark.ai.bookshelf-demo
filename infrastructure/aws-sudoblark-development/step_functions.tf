# CloudWatch Log Group for state machine execution history
resource "aws_cloudwatch_log_group" "state_machine" {
  for_each = { for sm in module.data.state_machines : sm.name => sm }

  name              = "/aws/states/${each.value.full_name}"
  retention_in_days = 365

  tags = {
    Name = "/aws/states/${each.value.full_name}"
  }
}

# Create all Step Functions state machines defined in the data module
resource "aws_sfn_state_machine" "state_machine" {
  for_each = { for sm in module.data.state_machines : sm.name => sm }

  name       = each.value.full_name
  role_arn   = aws_iam_role.role[each.value.iam_role_name].arn
  definition = each.value.definition
  type       = each.value.type

  logging_configuration {
    log_destination        = "${aws_cloudwatch_log_group.state_machine[each.key].arn}:*"
    include_execution_data = true
    level                  = "ALL"
  }

  tracing_configuration {
    enabled = true
  }

  tags = {
    Name = each.value.full_name
  }

  depends_on = [
    aws_iam_role.role,
    aws_iam_role_policy.inline_policy
  ]
}
