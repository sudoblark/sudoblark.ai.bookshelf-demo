/*
  Step Functions State Machines data structure definition:

  Each state machine object requires:
  - name (string): The state machine identifier (will be prefixed with account-project-application)
  - definition (string): Rendered ASL JSON via templatefile(); ASL source lives under application/step_functions/
  - iam_policy_statements (list(object)): IAM policy statements for the state machine execution role

  Optional fields:
  - description (string): Description of the state machine (default: "")

  Constraints:
  - State machine names must be unique within the configuration
  - Final name will be: account-project-application-name (all lowercase)
  - ASL template file must exist at application/step_functions/<name>.asl.json
*/

locals {
  step_functions = [
    {
      name        = "raw-to-enriched"
      description = "Processes raw book images to enrich with AI-extracted metadata"
      # templatefile variables grow as processor Lambdas are added in future PRs
      definition = templatefile("${path.module}/../../application/step_functions/raw-to-enriched.asl.json", {
        description            = "Processes raw book images to enrich with AI-extracted metadata"
        metadata_extractor_arn = "arn:aws:lambda:${data.aws_region.current.id}:${data.aws_caller_identity.current.account_id}:function:${local.lambdas_map["metadata-extractor"].full_name}"
      })
      iam_policy_statements = [
        {
          sid       = "InvokeMetadataExtractor"
          effect    = "Allow"
          actions   = ["lambda:InvokeFunction"]
          resources = ["arn:aws:lambda:*:*:function:*-bookshelf-demo-metadata-extractor"]
        }
      ]
    }
  ]
}
