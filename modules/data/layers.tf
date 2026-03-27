/*
  Lambda Layers data structure definition:

  Each layer object requires:
  - name (string): The layer identifier (will be prefixed with account-project-application)
  - zip_file_path (string): Path to the ZIP file containing the layer code

  Optional fields:
  - description (string): Description of the layer (default: "")
  - compatible_runtimes (list(string)): Compatible runtimes (default: ["python3.11"])

  Constraints:
  - Layer names must be unique within the configuration
  - Final layer name will be: account-project-application-name (all lowercase)
  - ZIP must be structured with a python/ directory at the root

  Example:
  {
    name          = "bookshelf-agent"
    description   = "BookshelfAgent pydantic-ai wrapper for book metadata extraction"
    zip_file_path = "../../lambda-packages/bookshelf-agent.zip"
  }
*/

locals {
  layers = [
    {
      name          = "bookshelf-agent"
      description   = "BookshelfAgent pydantic-ai wrapper for book metadata extraction"
      zip_file_path = "../../lambda-packages/bookshelf-agent.zip"
    }
  ]
}
