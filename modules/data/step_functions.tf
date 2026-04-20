locals {
  step_functions = [
    {
      name        = "enrichment"
      description = "Enrichment pipeline: generates embeddings for accepted book metadata"
      definition = jsonencode({
        Comment = "Enrichment pipeline for accepted book metadata"
        StartAt = "GenerateEmbedding"
        States = {
          GenerateEmbedding = {
            Type     = "Task"
            Resource = "arn:aws:lambda:${data.aws_region.current.id}:${data.aws_caller_identity.current.account_id}:function:${lower("${local.account}-${local.project}-${local.application}-embedding-generator")}"
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
          sid     = "InvokeEmbeddingGenerator"
          effect  = "Allow"
          actions = ["lambda:InvokeFunction"]
          resources = [
            "arn:aws:lambda:${data.aws_region.current.id}:${data.aws_caller_identity.current.account_id}:function:${lower("${local.account}-${local.project}-${local.application}-embedding-generator")}"
          ]
        },
      ]
    },
  ]
}
