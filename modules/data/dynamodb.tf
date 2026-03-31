/*
  DynamoDB Tables data structure definition:

  Each table object requires:
  - name (string): Table identifier (prefixed with account-project-application)
  - hash_key (string): Partition key attribute name
  - range_key (string): Sort key attribute name

  Optional fields:
  - billing_mode (string): "PAY_PER_REQUEST" or "PROVISIONED" (default: "PAY_PER_REQUEST")
  - attributes (list(object)): Attribute definitions for keys and GSI keys only
  - global_secondary_indexes (list(object)): GSI definitions

  Constraints:
  - Only attributes used as key or index keys need to be declared
  - billing_mode defaults to PAY_PER_REQUEST (no capacity planning required)
  - Final table name will be: account-project-application-name (all lowercase)
*/

locals {
  dynamodb_tables = [
    {
      name         = "ingestion-tracking"
      hash_key     = "upload_id"
      billing_mode = "PAY_PER_REQUEST"
      attributes = [
        { name = "upload_id", type = "S" },
        { name = "user_id", type = "S" },
      ]
      global_secondary_indexes = [
        {
          name            = "user_id-index"
          hash_key        = "user_id"
          range_key       = "upload_id"
          projection_type = "ALL"
        }
      ]
    }
  ]
}
