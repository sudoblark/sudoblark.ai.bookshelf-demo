locals {
  state_machines_map = { for sm in var.state_machines : sm.name => sm }
}

data "aws_iam_policy_document" "assume_role" {
  for_each = local.state_machines_map

  statement {
    effect = "Allow"
    principals {
      type        = "Service"
      identifiers = ["states.amazonaws.com"]
    }
    actions = ["sts:AssumeRole"]
  }
}

resource "aws_iam_role" "step_functions" {
  for_each = local.state_machines_map

  name               = each.value.role_name
  assume_role_policy = data.aws_iam_policy_document.assume_role[each.key].json

  tags = {
    Name = each.value.role_name
  }
}

data "aws_iam_policy_document" "step_functions_policy" {
  for_each = local.state_machines_map

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

resource "aws_iam_role_policy" "step_functions_policy" {
  for_each = local.state_machines_map

  name   = "${each.value.name}-policy"
  role   = aws_iam_role.step_functions[each.key].id
  policy = data.aws_iam_policy_document.step_functions_policy[each.key].json
}

resource "aws_sfn_state_machine" "state_machine" {
  for_each = local.state_machines_map

  name     = each.value.full_name
  role_arn = aws_iam_role.step_functions[each.key].arn

  definition = jsonencode({
    Comment = each.value.description
    StartAt = "ExtractMetadata"
    States = {
      ExtractMetadata = {
        Type     = "Task"
        Resource = "arn:aws:states:::lambda:invoke"
        Parameters = {
          FunctionName = each.value.metadata_extractor_arn
          "Payload.$"  = "$"
        }
        End = true
      }
    }
  })

  tags = {
    Name = each.value.full_name
  }

  depends_on = [
    aws_iam_role.step_functions,
    aws_iam_role_policy.step_functions_policy,
  ]
}
