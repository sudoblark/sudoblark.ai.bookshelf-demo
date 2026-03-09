# Bookshelf Demo - AWS ETL Pipeline

[![License][license-shield]][license-url]

<!-- PROJECT LOGO -->
<br />
<div align="center">
  <h3 align="center">Bookshelf Demo</h3>

  <p align="center">
    A cloud-native, event-driven ETL pipeline for extracting book metadata from images using AWS Bedrock and storing results in Parquet format.
    <br />
    <a href="#getting-started"><strong>Get Started »</strong></a>
    <br />
    <br />
    <a href="https://github.com/sudoblark/sudoblark.ai.bookshelf-demo/issues">Report Bug</a>
    ·
    <a href="https://github.com/sudoblark/sudoblark.ai.bookshelf-demo/issues">Request Feature</a>
  </p>
</div>

<!-- TABLE OF CONTENTS -->
<details>
  <summary>Table of Contents</summary>
  <ol>
    <li><a href="#about-the-project">About The Project</a></li>
    <li><a href="#architecture">Architecture</a></li>
    <li><a href="#etl-pipeline-flow">ETL Pipeline Flow</a></li>
    <li><a href="#infrastructure">Infrastructure</a></li>
    <li><a href="#metadata-schema">Metadata Schema</a></li>
    <li><a href="#prerequisites">Prerequisites</a></li>
    <li><a href="#deployment">Deployment</a></li>
    <li><a href="#usage">Usage</a></li>
    <li><a href="#project-structure">Project Structure</a></li>
    <li><a href="#future-enhancements">Future Enhancements</a></li>
    <li><a href="#license">License</a></li>
  </ol>
</details>

## About The Project

The Bookshelf Demo is a fully automated, cloud-native ETL pipeline that:

- Accepts ZIP files containing book cover images
- Extracts images to a raw storage layer
- Uses AWS Bedrock (Claude 3 Haiku) to intelligently extract book metadata from images
- Stores structured metadata in Parquet format for analytics

This project demonstrates data-driven Terraform patterns and AWS serverless architecture best practices.

## Architecture

The infrastructure follows a **data-driven Terraform pattern** with three distinct layers:

1. **Data Layer** (modules/data/*.tf): Defines infrastructure as simple data structures
2. **Infrastructure Modules Layer**: Reusable Terraform modules that create AWS resources
3. **Instantiation Layer** (infrastructure/*/): Wires data module to infrastructure modules

### Directory Structure

```
bookshelf-demo/
├── modules/
│   └── data/                    # Infrastructure as data
│       ├── buckets.tf           # S3 bucket definitions
│       ├── iam_roles.tf         # IAM role definitions
│       ├── lambdas.tf           # Lambda function definitions
│       ├── notifications.tf     # S3 event notification definitions
│       ├── infrastructure.tf    # Data enrichment logic
│       └── outputs.tf           # Enriched data outputs
├── infrastructure/
│   └── aws-sudoblark-development/
│       ├── main.tf              # Provider & backend config
│       ├── data.tf              # Data module instantiation
│       ├── s3.tf                # S3 bucket resources
│       ├── iam.tf               # IAM role resources
│       ├── lambda.tf            # Lambda function resources
│       └── notifications.tf     # S3 notification resources
└── lambda-packages/
    ├── unzip-processor/         # ZIP extraction Lambda
    │   └── lambda_function.py
    └── metadata-extractor/      # Bedrock metadata extraction Lambda
        └── lambda_function.py
```

## ETL Pipeline Flow

```
┌───────────┐    S3 Event    ┌────────────────┐
│  Upload   │───────────────►│ Unzip Processor│
│    ZIP    │                 │     Lambda     │
└───────────┘                 └────────┬───────┘
                                       │
                                       ▼
                              ┌────────────────┐
                              │  S3 Raw Bucket │
                              │    (images)    │
                              └────────┬───────┘
                                       │ S3 Event
                                       ▼
                          ┌────────────────────────┐
                          │ Metadata Extractor     │
                          │      Lambda            │
                          └────────┬───────────────┘
                                   │
                    ┌──────────────┴──────────────┐
                    │                             │
                    ▼                             ▼
            ┌──────────────┐          ┌─────────────────┐
            │AWS Bedrock   │          │ S3 Processed    │
            │Claude Haiku  │          │   Bucket        │
            └──────────────┘          │  (parquet)      │
                                      └─────────────────┘
```

### Pipeline Stages

1. **Landing Stage**: ZIP files are uploaded to the landing bucket
2. **Extraction Stage**: Unzip processor Lambda extracts image files to raw bucket
3. **Metadata Extraction Stage**: Metadata extractor Lambda:
   - Downloads images from raw bucket
   - Resizes images for Bedrock API efficiency
   - Calls Claude 3 Haiku to extract book metadata
   - Writes structured metadata to Parquet format
4. **Storage Stage**: Parquet files stored in processed bucket for analytics

## Infrastructure

### S3 Buckets

- **aws-sudoblark-development-bookshelf-demo-landing**: Accepts ZIP file uploads
- **aws-sudoblark-development-bookshelf-demo-raw**: Stores extracted images
- **aws-sudoblark-development-bookshelf-demo-processed**: Stores Parquet metadata files
- **aws-sudoblark-development-bookshelf-demo-athena-results**: Stores Athena query results

### Lambda Functions

#### Unzip Processor
- **Runtime**: Python 3.11
- **Memory**: 512 MB
- **Timeout**: 60 seconds
- **Trigger**: S3 ObjectCreated events on .zip files in landing bucket
- **Function**: Extracts image files from ZIP archives

#### Metadata Extractor
- **Runtime**: Python 3.11
- **Memory**: 1024 MB
- **Timeout**: 300 seconds (5 minutes)
- **Trigger**: S3 ObjectCreated events on image files in raw bucket
- **Function**: Extracts book metadata using Bedrock and writes to Parquet
- **Lambda Layers**:
  - AWS SDK for pandas (Python 3.11)
  - Pillow for image processing

### IAM Roles

Each Lambda function has a dedicated IAM role with least-privilege permissions:
- Unzip processor: Read from landing, write to raw
- Metadata extractor: Read from raw, write to processed, invoke Bedrock model
- Glue crawler: Read/list processed bucket, write to Glue Data Catalog

### AWS Glue

#### Glue Database
- **aws-sudoblark-development-bookshelf-demo-bookshelf**: Database for organizing book metadata tables

#### Glue Crawler
- **aws-sudoblark-development-bookshelf-demo-bookshelf-metadata-crawler**: Automatically discovers schema and partitions from Parquet files
- **Schedule**: Daily at 3 AM UTC
- **Target**: Processed bucket with Parquet files
- **Output**: Tables in the bookshelf database

### AWS Athena

#### Athena Workgroup
- **aws-sudoblark-development-bookshelf-demo-bookshelf-analytics**: Workgroup for querying book metadata
- **Query Results**: Stored in athena-results bucket
- **CloudWatch Metrics**: Enabled for monitoring query performance

## Metadata Schema

Parquet files contain the following fields:

| Field | Type | Description |
|-------|------|-------------|
| id | string | Unique identifier (UUID) |
| filename | string | Original image filename |
| title | string | Book title |
| author | string | Author name |
| isbn | string | ISBN (digits only) |
| publisher | string | Publisher name |
| published_year | integer/null | Publication year |
| description | string | Brief book description |
| processed_at | string | ISO 8601 timestamp of processing |

## Prerequisites

- **Terraform**: ~> 1.14
- **AWS Account**: With Bedrock access in eu-west-2
- **AWS CLI**: Configured with appropriate credentials
- **Python**: 3.11 (for local Lambda development)
- **IAM Role**: GitHub CI/CD role with deployment permissions

### Bedrock Model Access

Ensure you have access to the Claude 3 Haiku model in your AWS account:
- Model ID: anthropic.claude-3-haiku-20240307-v1:0
- Region: eu-west-2

## Deployment

### 1. Package Lambda Functions

```bash
# Unzip processor
cd lambda-packages/unzip-processor
pip install -r requirements.txt -t .
zip -r ../unzip-processor.zip .
cd ../..

# Metadata extractor
cd lambda-packages/metadata-extractor
pip install -r requirements.txt -t .
zip -r ../metadata-extractor.zip .
cd ../..
```

### 2. Initialize Terraform

```bash
cd infrastructure/aws-sudoblark-development
terraform init
```

### 3. Plan Deployment

```bash
terraform plan
```

### 4. Apply Infrastructure

```bash
terraform apply
```

### 5. Verify Deployment

Check that resources were created:
```bash
# List buckets
aws s3 ls | grep bookshelf-demo

# List Lambda functions
aws lambda list-functions --query 'Functions[?contains(FunctionName, `bookshelf-demo`)]'
```

## Usage

### Upload ZIP Files

Upload a ZIP file containing book cover images to the landing bucket:

```bash
# Create a test ZIP
zip books.zip cover1.jpg cover2.jpg cover3.jpg

# Upload to landing bucket
aws s3 cp books.zip s3://aws-sudoblark-development-bookshelf-demo-landing/
```

### Monitor Processing

Watch Lambda logs:
```bash
# Unzip processor logs
aws logs tail /aws/lambda/aws-sudoblark-development-bookshelf-demo-unzip-processor --follow

# Metadata extractor logs
aws logs tail /aws/lambda/aws-sudoblark-development-bookshelf-demo-metadata-extractor --follow
```

### Retrieve Results

Download processed Parquet files:
```bash
# List processed files
aws s3 ls s3://aws-sudoblark-development-bookshelf-demo-processed/

# Download a specific file
aws s3 cp s3://aws-sudoblark-development-bookshelf-demo-processed/metadata_20260209_120000_uuid.parquet .
```

### Read Parquet Files

Using Python:
```python
import pandas as pd

df = pd.read_parquet("metadata_20260209_120000_uuid.parquet")
print(df)
```

### Query with Athena

After the Glue crawler runs (scheduled daily at 3 AM UTC or run manually), query the data with Athena:

```sql
-- Set workgroup
-- Use: aws-sudoblark-development-bookshelf-demo-bookshelf-analytics

-- Query all books
SELECT * FROM "aws-sudoblark-development-bookshelf-demo-bookshelf"."processed"
LIMIT 10;

-- Find books by author
SELECT title, author, published_year, isbn
FROM "aws-sudoblark-development-bookshelf-demo-bookshelf"."processed"
WHERE author LIKE '%author_name%';

-- Count books by publisher
SELECT publisher, COUNT(*) as book_count
FROM "aws-sudoblark-development-bookshelf-demo-bookshelf"."processed"
GROUP BY publisher
ORDER BY book_count DESC;

-- Books published after 2020
SELECT title, author, published_year
FROM "aws-sudoblark-development-bookshelf-demo-bookshelf"."processed"
WHERE published_year > 2020
ORDER BY published_year DESC;
```

**Manually run the Glue crawler:**
```bash
aws glue start-crawler --name aws-sudoblark-development-bookshelf-demo-bookshelf-metadata-crawler
```

## Project Structure

```
bookshelf-demo/
├── infrastructure/                      # Terraform infrastructure code
│   └── aws-sudoblark-development/      # Environment-specific instantiation
│       ├── main.tf                     # Provider & backend configuration
│       ├── data.tf                     # Data module instantiation
│       ├── s3.tf                       # S3 bucket resources
│       ├── iam.tf                      # IAM role resources
│       ├── lambda.tf                   # Lambda function resources
│       ├── notifications.tf            # S3 event notification resources
│       ├── athena_workgroups.tf        # Athena workgroup resources
│       ├── glue_databases.tf           # Glue database resources
│       ├── glue_crawlers.tf            # Glue crawler resources
│       ├── glue_catalog_encryption.tf  # Glue Data Catalog encryption
│       ├── application_registry.tf     # AWS Service Catalog registration
│       ├── variables.tf                # Input variables
│       └── outputs.tf                  # Output values
│
├── modules/                            # Reusable Terraform modules
│   └── data/                           # Infrastructure as data definitions
│       ├── buckets.tf                  # S3 bucket data structures
│       ├── iam_roles.tf                # IAM role data structures
│       ├── lambdas.tf                  # Lambda function data structures
│       ├── notifications.tf            # S3 notification data structures
│       ├── athena_workgroups.tf        # Athena workgroup data structures
│       ├── glue_databases.tf           # Glue database data structures
│       ├── glue_crawlers.tf            # Glue crawler data structures
│       ├── infrastructure.tf           # Data enrichment & reference resolution
│       ├── outputs.tf                  # Enriched data outputs
│       └── defaults.tf                 # Default configuration values
│
├── lambda-packages/                    # Lambda function source code
│   ├── unzip-processor/
│   │   ├── lambda_function.py          # ZIP extraction handler
│   │   ├── requirements.txt            # Python dependencies
│   │   └── README.md                   # Function documentation
│   └── metadata-extractor/
│       ├── lambda_function.py          # Bedrock metadata extraction handler
│       ├── requirements.txt            # Python dependencies (includes Pillow)
│       └── README.md                   # Function documentation
│
├── .github/                            # GitHub configuration
│   ├── copilot-instructions.md         # GitHub Copilot main instructions
│   ├── workflows/
│   │   └── pull-request.yaml           # CI/CD pipeline for Terraform
│   └── instructions/
│       ├── terraform.md                # Terraform coding standards
│       ├── python.md                   # Python coding standards
│       └── readme.md                   # Documentation standards
│
├── docs/                               # Project documentation
│   ├── architecture.md                 # Architecture deep-dive
│   ├── demo-setup.md                   # Demo setup guide
│   └── CODEOWNERS                      # Code ownership definitions
│
├── .gitignore                          # Git ignore patterns
├── .pre-commit-config.yaml             # Pre-commit hooks (linting, formatting)
├── pyproject.toml                      # Python tooling configuration
├── Makefile                            # Common development commands
├── LICENSE.txt                         # MIT License
└── README.md                           # This file
```

## Future Enhancements

Planned additions (not yet implemented):

- **AWS Glue**: Crawlers for automatic schema discovery
- **AWS Athena**: SQL queries over Parquet data
- **Prompt Refinement**: Improved metadata extraction accuracy
- **Batch Processing**: Support for large-scale bulk uploads
- **Data Quality**: Validation and confidence scoring
- **Web UI**: Frontend for browsing extracted metadata

## License

Distributed under the MIT License. See [LICENSE.txt](LICENSE.txt) for more information.

---

<!-- MARKDOWN LINKS & IMAGES -->
[license-shield]: https://img.shields.io/github/license/sudoblark/sudoblark.ai.bookshelf-demo.svg
[license-url]: https://github.com/sudoblark/sudoblark.ai.bookshelf-demo/blob/main/LICENSE.txt




| Component | AWS | GCP | Azure |
|-----------|-----|-----|-------|
| **Core Data Lake** | S3 | Cloud Storage | Azure Data Lake Storage Gen2 |
| **Serverless Compute** | Lambda | Cloud Functions / Cloud Run | Azure Functions |
| **AI Inference** | Bedrock (Vision) | Vertex AI Vision | Azure AI Vision |
| **Analytical Layer** | Athena | BigQuery | Synapse Analytics |
| **File Storage Format** | Parquet | Parquet | Parquet |
