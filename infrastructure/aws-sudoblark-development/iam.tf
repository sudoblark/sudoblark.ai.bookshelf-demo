# Create all IAM roles defined in the data module
resource "aws_iam_role" "role" {
  for_each = { for role in module.data.iam_roles : role.name => role }

  name               = each.value.full_name
  assume_role_policy = each.value.assume_role_policy

  tags = {
    Name = each.value.full_name
  }
}

resource "aws_iam_role_policy" "inline_policy" {
  for_each = merge([
    for role in module.data.iam_roles : {
      for policy in role.inline_policies :
      "${role.name}/${policy.name}" => {
        role_name = role.name
        policy    = policy
      }
    }
  ]...)

  name   = each.value.policy.name
  role   = aws_iam_role.role[each.value.role_name].id
  policy = each.value.policy.policy
}

resource "aws_iam_role_policy_attachment" "managed_policy" {
  for_each = merge([
    for role in module.data.iam_roles : {
      for idx, policy_arn in role.managed_policy_arns :
      "${role.name}/${idx}" => {
        role_name  = role.name
        policy_arn = policy_arn
      }
    }
  ]...)

  role       = aws_iam_role.role[each.value.role_name].name
  policy_arn = each.value.policy_arn
}
