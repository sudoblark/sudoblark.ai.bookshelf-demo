/*
  Glue Database data structure definition:

  Each object defines a Glue database for the AWS Glue Data Catalog.
  Databases organize tables and are used by crawlers and Athena queries.

  Required fields:
  - name (string): Short name for the database (will be prefixed with account-project-application)

  Optional fields:
  - description (string): Human-readable description of the database purpose (default: "")

  Constraints:
  - name must be lowercase and contain only letters, numbers, hyphens, and underscores
  - name will be prefixed with account-project-application for uniqueness
  - description should clearly explain the database's purpose and contents

  Example:
  {
    name        = "analytics"
    description = "Analytics database for ETL pipeline data"
  }
*/

locals {
  glue_databases = [
    {
      name        = "bookshelf"
      description = "Database for book metadata extracted from cover images"
    }
  ]
}
