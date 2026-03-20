/*
  Step Functions State Machine data structure definition:

  Each state machine object requires:
  - name (string): The state machine identifier (will be prefixed with account-project-application)
  - definition (string): ASL JSON definition (use templatefile() for dynamic ARNs)
  - iam_role_name (string): Name of the IAM role to use (must exist in iam_roles locals)

  Optional fields:
  - description (string): Description of the state machine (default: "")
  - type (string): "STANDARD" or "EXPRESS" (default: "STANDARD")

  Expected execution input:
  {
    "bucket": "<raw-bucket-name>",
    "key":    "<s3-key-of-image>"
  }
*/

locals {
  state_machines = [
    {
      name          = "raw-to-enriched"
      description   = "Enrichment pipeline: invokes metadata-extractor for a single book cover image from the raw bucket"
      type          = "STANDARD"
      iam_role_name = "raw-to-enriched-role"

      definition = templatefile("${path.module}/state-machines/raw-to-enriched.asl.json", {
        metadata_extractor_arn = "arn:aws:lambda:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:function:${local.lambdas_map["metadata-extractor"].full_name}"
      })
    }
  ]
}
