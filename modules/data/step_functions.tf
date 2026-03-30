/*
  Step Functions State Machines data structure definition:

  Each state machine object requires:
  - name (string): The state machine identifier (will be prefixed with account-project-application)
  - metadata_extractor_name (string): Name of the Lambda to invoke for metadata extraction

  Optional fields:
  - description (string): Description of the state machine (default: "")
  - iam_policy_statements (list(object)): IAM policy statements for the state machine execution role

  Constraints:
  - State machine names must be unique within the configuration
  - Final name will be: account-project-application-name (all lowercase)
  - metadata_extractor_name must reference an existing Lambda in the lambdas local
*/

locals {
  step_functions = [
    {
      name                    = "raw-to-enriched"
      description             = "Processes raw book images to enrich with AI-extracted metadata"
      metadata_extractor_name = "metadata-extractor"
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
