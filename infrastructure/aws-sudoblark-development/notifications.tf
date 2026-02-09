# Create S3 bucket notifications to trigger Lambda functions
resource "aws_lambda_permission" "s3_invoke" {
  for_each = merge([
    for notification in module.data.notifications : {
      for lambda_notif in notification.lambda_notifications_resolved :
      "${notification.bucket_name}/${lambda_notif.lambda_name}" => {
        bucket_name         = notification.bucket_name
        lambda_name         = lambda_notif.lambda_name
        lambda_function_arn = lambda_notif.lambda_function_arn
      }
    }
  ]...)

  statement_id  = "AllowS3Invoke-${each.value.bucket_name}"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.lambda[each.value.lambda_name].function_name
  principal     = "s3.amazonaws.com"
  source_arn    = aws_s3_bucket.bucket[each.value.bucket_name].arn
}

resource "aws_s3_bucket_notification" "notification" {
  for_each = { for notification in module.data.notifications : notification.bucket_name => notification }

  bucket = aws_s3_bucket.bucket[each.key].id

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
