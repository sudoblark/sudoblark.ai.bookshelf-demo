locals {
  # Deduplicate bucket→lambda pairs — multiple suffix filters for the same lambda
  # produce one IAM permission, not one per filter.
  unique_lambda_permissions = {
    for item in distinct(flatten([
      for notification in var.notifications : [
        for lambda_notif in notification.lambda_notifications_resolved : {
          key                 = "${notification.bucket_name}/${lambda_notif.lambda_name}"
          bucket_name         = notification.bucket_name
          lambda_name         = lambda_notif.lambda_name
          lambda_function_arn = lambda_notif.lambda_function_arn
        }
      ]
    ])) : item.key => item
  }
}

resource "aws_lambda_permission" "s3_invoke" {
  for_each = local.unique_lambda_permissions

  statement_id  = "AllowS3Invoke-${each.value.bucket_name}"
  action        = "lambda:InvokeFunction"
  function_name = each.value.lambda_function_arn
  principal     = "s3.amazonaws.com"
  source_arn    = var.bucket_arns[each.value.bucket_name]
}

resource "aws_s3_bucket_notification" "notification" {
  for_each = { for notification in var.notifications : notification.bucket_name => notification }

  bucket = var.bucket_ids[each.key]

  dynamic "lambda_function" {
    for_each = each.value.lambda_notifications_resolved

    content {
      lambda_function_arn = lambda_function.value.lambda_function_arn
      events              = lambda_function.value.events
      filter_prefix       = lambda_function.value.filter_prefix
      filter_suffix       = lambda_function.value.filter_suffix
    }
  }

  depends_on = [aws_lambda_permission.s3_invoke]
}
