locals {
  step_functions = [
    {
      name        = "enrichment"
      description = "Enriches ingested files into their final processed form"
      definition = jsonencode({
        Comment = "Enrichment pipeline for accepted book metadata"
        StartAt = "CopyToProcessed"
        States = {
          CopyToProcessed = {
            Type     = "Task"
            Resource = "arn:aws:lambda:${data.aws_region.current.id}:${data.aws_caller_identity.current.account_id}:function:${lower("${local.account}-${local.project}-${local.application}-raw-to-processed-copy")}"
            Next     = "GenerateEmbedding"
            Retry = [
              {
                ErrorEquals     = ["Lambda.ServiceException", "Lambda.AWSLambdaException", "Lambda.TooManyRequestsException"]
                IntervalSeconds = 2
                MaxAttempts     = 3
                BackoffRate     = 2
              }
            ]
          }
          GenerateEmbedding = {
            Type     = "Task"
            Resource = "arn:aws:lambda:${data.aws_region.current.id}:${data.aws_caller_identity.current.account_id}:function:${lower("${local.account}-${local.project}-${local.application}-vector-generator")}"
            End      = true
            Retry = [
              {
                ErrorEquals     = ["Lambda.ServiceException", "Lambda.AWSLambdaException", "Lambda.TooManyRequestsException"]
                IntervalSeconds = 2
                MaxAttempts     = 3
                BackoffRate     = 2
              }
            ]
          }
        }
      })
      iam_policy_statements = [
        {
          sid     = "InvokeCopyToProcessed"
          effect  = "Allow"
          actions = ["lambda:InvokeFunction"]
          resources = [
            "arn:aws:lambda:${data.aws_region.current.id}:${data.aws_caller_identity.current.account_id}:function:${lower("${local.account}-${local.project}-${local.application}-raw-to-processed-copy")}"
          ]
        },
        {
          sid     = "InvokeVectorGenerator"
          effect  = "Allow"
          actions = ["lambda:InvokeFunction"]
          resources = [
            "arn:aws:lambda:${data.aws_region.current.id}:${data.aws_caller_identity.current.account_id}:function:${lower("${local.account}-${local.project}-${local.application}-vector-generator")}"
          ]
        },
      ]
    },
  ]
}
