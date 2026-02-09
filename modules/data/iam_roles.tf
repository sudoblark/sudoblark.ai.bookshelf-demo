/*
  IAM Roles data structure definition:

  Each role object requires:
  - name (string): The IAM role identifier (will be prefixed with account-project-application)
  - assume_role_services (list(string)): AWS services that can assume this role

  Optional fields:
  - inline_policies (list(object)): Inline IAM policies to attach (default: [])
    - name (string): Policy name
    - policy_statements (list(object)): Policy statements
      - effect (string): "Allow" or "Deny"
      - actions (list(string)): IAM actions
      - resources (list(string)): ARNs or wildcards
  - managed_policy_arns (list(string)): AWS managed policy ARNs to attach (default: [])

  Constraints:
  - Role names must be unique within the configuration
  - Final role name will be: account-project-application-name (all lowercase)
  - assume_role_services typically includes: "lambda.amazonaws.com", "ec2.amazonaws.com", etc.

  Example:
  {
    name = "unzip-processor-role"
    assume_role_services = ["lambda.amazonaws.com"]
    inline_policies = [
      {
        name = "s3-access"
        policy_statements = [
          {
            effect = "Allow"
            actions = ["s3:GetObject"]
            resources = ["arn:aws:s3:::bucket-name/*"]
          }
        ]
      }
    ]
    managed_policy_arns = [
      "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
    ]
  }
*/

locals {
  # Define IAM roles for Lambda functions
  iam_roles = [
    {
      name                 = "unzip-processor-role"
      assume_role_services = ["lambda.amazonaws.com"]
      inline_policies = [
        {
          name = "s3-access"
          policy_statements = [
            {
              effect = "Allow"
              actions = [
                "s3:GetObject"
              ]
              resources = [
                "arn:aws:s3:::${local.account}-${local.project}-${local.application}-landing/*"
              ]
            },
            {
              effect = "Allow"
              actions = [
                "s3:PutObject"
              ]
              resources = [
                "arn:aws:s3:::${local.account}-${local.project}-${local.application}-raw/*"
              ]
            }
          ]
        }
      ]
      managed_policy_arns = [
        "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
      ]
    },
    {
      name                 = "metadata-extractor-role"
      assume_role_services = ["lambda.amazonaws.com"]
      inline_policies = [
        {
          name = "s3-bedrock-access"
          policy_statements = [
            {
              effect = "Allow"
              actions = [
                "s3:GetObject"
              ]
              resources = [
                "arn:aws:s3:::${local.account}-${local.project}-${local.application}-raw/*"
              ]
            },
            {
              effect = "Allow"
              actions = [
                "s3:PutObject"
              ]
              resources = [
                "arn:aws:s3:::${local.account}-${local.project}-${local.application}-processed/*"
              ]
            },
            {
              effect = "Allow"
              actions = [
                "bedrock:InvokeModel"
              ]
              resources = [
                "arn:aws:bedrock:eu-west-2::foundation-model/anthropic.claude-3-haiku-20240307-v1:0"
              ]
            }
          ]
        }
      ]
      managed_policy_arns = [
        "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
      ]
    }
  ]
}
