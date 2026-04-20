<!-- Improved compatibility of back to top link -->
<a id="readme-top"></a>

<!-- PROJECT SHIELDS -->
[![CI Status][ci-shield]][ci-url]
[![Issues][issues-shield]][issues-url]
[![MIT License][license-shield]][license-url]
[![LinkedIn][linkedin-shield]][linkedin-url]

<!-- PROJECT LOGO -->
<br />
<div align="center">
  <h1>📚</h1>

  <h3 align="center">Bookshelf Demo</h3>

  <p align="center">
    A live demo showing how AI agents plug into existing serverless workflows — and how giving them business context via tools is simpler than you think.
    <br />
    <a href="https://github.com/sudoblark/sudoblark.ai.bookshelf-demo"><strong>Explore the docs »</strong></a>
    <br />
    <br />
    <a href="https://github.com/sudoblark/sudoblark.ai.bookshelf-demo">View Demo</a>
    ·
    <a href="https://github.com/sudoblark/sudoblark.ai.bookshelf-demo/issues/new?labels=bug&template=bug-report---.md">Report Bug</a>
    ·
    <a href="https://github.com/sudoblark/sudoblark.ai.bookshelf-demo/issues/new?labels=enhancement&template=feature-request---.md">Request Feature</a>
  </p>
</div>

<!-- TABLE OF CONTENTS -->
<details>
  <summary>Table of Contents</summary>
  <ol>
    <li>
      <a href="#about-the-project">About The Project</a>
      <ul>
        <li><a href="#repository-structure-mono-repo-vs-micro-repos">Repository Structure: Mono-repo vs Micro-repos</a></li>
        <li><a href="#built-with">Built With</a></li>
      </ul>
    </li>
    <li><a href="#architecture">Architecture</a></li>
    <li><a href="#getting-started">Getting Started</a></li>
    <li><a href="#testing">Testing</a></li>
    <li><a href="#deployment">Deployment</a></li>
    <li><a href="#current-limitations">Current Limitations</a></li>
    <li><a href="#license">License</a></li>
    <li><a href="#contact">Contact</a></li>
    <li><a href="#acknowledgments">Acknowledgments</a></li>
  </ol>
</details>

<!-- ABOUT THE PROJECT -->
## About The Project

> **📢 Sudoblark Workshop Repository**
>
> This repository is the **live demo used in Sudoblark's AI engineering workshops and conference talks**. It is designed to be explored alongside a presenter — the code, architecture decisions, and documentation are all written with that context in mind.
>
> **Found this independently?** If you arrived here from the [AI Vision Inference blog series](https://sudoblark.com/blog/series/ai-vision-inference/), you're in the right place — the series walks through the concepts this demo illustrates. If you've stumbled across it another way, everything is deployable and self-contained, but it'll make most sense as a companion to the workshop or series.

> **⚠️ Infrastructure Configuration**
>
> This repository is pre-configured to deploy to **Sudoblark's AWS infrastructure**. To deploy to your own AWS account, you'll need to modify the Terraform configuration files (account names, bucket names, state backend, etc.).

A lot of AI integration demos exist in isolation — a model, a prompt, a response. This one doesn't. It shows an agent embedded in a real serverless architecture: uploading files, querying storage, tracking pipeline state. The book cataloguing domain is intentionally mundane; the point is to show the seams where AI fits into systems you'd actually build, not to impress with the use case.

### What the demo shows

| Feature | In this demo | The general pattern |
|---|---|---|
| **Book upload via presigned S3 URL** | Upload a book cover image directly from the browser to S3 | File ingestion without routing through your API — a standard serverless pattern and a natural handoff point into agent workflows |
| **AI metadata extraction** | An agent extracts title, author, and ISBN from a cover image using OCR, ISBN lookup, and metadata search tools | An agent given a focused toolset to complete a well-scoped task; transparent about what it called and why |
| **Bookshelf dashboard** | Browse and search the books you've catalogued | The read path of a data pipeline surfaced in a UI — confirming that what went in came out correctly |
| **Ops dashboard** | Track every upload through its pipeline stages, including failures and abandoned sessions | Observability for agent-driven workflows; making the pipeline's state visible rather than trusting it blindly |
| **Ook Chat** | Ask questions about your book collection in natural language | An agent reusing the same primitive from extraction, now handed broader domain tools — showing that business context is just another toolset |

**Not on AWS?** The demo runs on AWS, but every pattern it demonstrates has a direct equivalent on GCP and Azure. The services are different; the architecture is the same.

| Concept | AWS (this demo) | GCP | Azure |
|---|---|---|---|
| Object storage | S3 | Cloud Storage | Blob Storage |
| Container hosting (streaming API) | ECS Fargate¹ | Cloud Run | Container Instances |
| Managed AI model | Bedrock (Claude) | Vertex AI | Azure OpenAI |
| NoSQL database | DynamoDB | Firestore | Cosmos DB |
| IaC | Terraform | Terraform | Terraform |

_¹ In this demo the streaming API runs locally via Docker to avoid hosting costs. ECS Fargate is the production equivalent._

<p align="right">(<a href="#readme-top">back to top</a>)</p>

### Repository Structure: Mono-repo vs Micro-repos

Everything lives in one repository for convenience — a single clone, a single `terraform apply`, and a single test run gets the full system running. In a real production setup, each component would have its own repository, pipeline, and release cadence.

| This repo | Component | What it would be in production |
|---|---|---|
| `application/backend/streaming-agent/` | Streaming API | In production, a separately deployed container service — streaming requires persistent connections, not Lambda |
| `application/backend/common/` | Shared utilities | A versioned internal package imported by other services |
| `application/frontend/` | React UI | A separately deployed frontend, likely on a CDN |

The Terraform in `modules/` and `infrastructure/` is similarly coupled into one state for simplicity. In production each service would manage its own infrastructure, but splitting that state here would add complexity without adding anything to the workshop.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

### Built With

* [![Python][Python-badge]][Python-url]
* [![AWS][AWS-badge]][AWS-url]
* [![Terraform][Terraform-badge]][Terraform-url]
* [![GitHub Actions][GitHub-Actions-badge]][GitHub-Actions-url]

<p align="right">(<a href="#readme-top">back to top</a>)</p>


<!-- ARCHITECTURE -->
## Architecture

React frontend, FastAPI streaming backend, S3 for storage, DynamoDB for tracking, Bedrock for the model, Textract for OCR. The infrastructure follows Sudoblark's three-layer Terraform pattern — the [blog post](https://sudoblark.com/blog/three-tier-terraform-data-pattern/) covers how that works.

### API Endpoints

| Endpoint | Method | Purpose |
|---|---|---|
| `/health` | GET | Health check |
| `/api/upload/presigned` | GET | Generate presigned S3 PUT URL for direct browser upload |
| `/api/metadata/extract` | POST | Extract metadata from a cover image, or continue a refinement conversation |
| `/api/metadata/accept` | POST | Save confirmed metadata to S3 |
| `/api/ops/files` | GET | List all uploads with pipeline stage status |
| `/api/ops/files/{file_id}` | GET | Get stage detail for a single upload |
| `/api/bookshelf/overview` | GET | Collection statistics |
| `/api/bookshelf/catalogue` | GET | Paginated book list |
| `/api/bookshelf/search` | GET | Search by title or author |
| `/api/ook/chat` | POST | Ook Chat — streaming conversational agent |

## Getting Started

**⚠️ All setup, installation, and local development instructions are in [docs/demo-execution.md](docs/demo-execution.md)**

This includes:
- Prerequisites and tool verification
- Step-by-step installation and environment setup
- Credential export for AWS SSO
- Running backend and frontend locally
- 5 complete end-to-end test scenarios
- Debugging checklist and performance notes

Start there for hands-on guidance.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

<!-- TESTING -->
## Testing

This project follows Sudoblark's Python quality standards with comprehensive test coverage.

### Running Tests

```sh
# Run all tests with coverage
pytest --cov=application/backend --cov-report=html --cov-report=term-missing

# Run a specific test file
pytest tests/backend/streaming-agent/test_metadata_handlers.py -v

# Run with verbose output
pytest tests/ -v
```

### Test Coverage Requirements

- **Minimum Coverage:** 80%
- **Current Coverage:** Check CI/CD badge at top of README
- **Coverage Report:** Generated in `htmlcov/index.html` after running tests

### Linting and Security

```sh
# Format code with Black
black application/backend/ tests/

# Sort imports
isort application/backend/ tests/

# Lint with Flake8
flake8 application/backend/ tests/

# Type checking with mypy (requires boto3-stubs)
pip install 'boto3-stubs[s3,bedrock-runtime]'
mypy application/backend/

# Security scan with Bandit
bandit -r application/backend/
```

**CI/CD:** All checks run automatically on pull requests. See `.github/workflows/pull-request.yaml`.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

<!-- DEPLOYMENT -->
## Deployment

This project uses **GitHub Actions** for continuous integration and deployment:

**Pull Request Workflow** (`.github/workflows/pull-request.yaml`):
- Python linting (Black, isort, Flake8)
- Security scanning (Bandit)
- Unit tests with coverage reporting
- Terraform validation and plan

**Manual Deployment Workflows**:
- `apply.yaml` - Deploy infrastructure to AWS
- `destroy.yaml` - Tear down infrastructure (use with caution)

For manual deployment and verification steps, see [docs/demo-execution.md](docs/demo-execution.md).

<p align="right">(<a href="#readme-top">back to top</a>)</p>

## Current Limitations

Everything in the demo works. Some things are deliberately simplified compared to a production system — either to keep the demo self-contained, or because the complexity would obscure the concepts being illustrated.

| Area | Demo approach | Production equivalent |
|---|---|---|
| **Bookshelf queries** | S3 bucket scan on every request | DynamoDB reads (see ADR-0001) — fine at demo scale, expensive at production scale |
| **Session state** | In-process only — lost on restart | Persistent store (Redis, DynamoDB) |
| **Streaming backend** | Local Docker | ECS Fargate — streaming requires persistent connections, not Lambda |
| **Authentication** | None — all endpoints public | Cognito with user scoping — adds cost and complexity with no demo value |

<p align="right">(<a href="#readme-top">back to top</a>)</p>

For troubleshooting, debugging tips, and common issues, see [docs/demo-execution.md](docs/demo-execution.md).

<!-- LICENSE -->
## License

Distributed under the MIT License. See `LICENSE.txt` for more information.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

<!-- CONTACT -->
## Contact

**Sudoblark Ltd** - Enterprise AI & Cloud Solutions

- 🌐 Website: [sudoblark.com](https://sudoblark.com)
- 💼 LinkedIn: [Sudoblark](https://linkedin.com/company/sudoblark)
- 📧 Email: [hello@sudoblark.com](mailto:hello@sudoblark.com)
- 🐙 GitHub: [@sudoblark](https://github.com/sudoblark)

**Project Link:** [https://github.com/sudoblark/sudoblark.ai.bookshelf-demo](https://github.com/sudoblark/sudoblark.ai.bookshelf-demo)

<p align="right">(<a href="#readme-top">back to top</a>)</p>

<!-- ACKNOWLEDGMENTS -->
## Acknowledgments

* [AWS Bedrock](https://aws.amazon.com/bedrock/) - Claude foundation models
* [Terraform](https://www.terraform.io/) - Infrastructure as Code
* [GitHub Actions](https://github.com/features/actions) - CI/CD automation
* [pytest](https://pytest.org/) - Python testing framework
* [Best-README-Template](https://github.com/othneildrew/Best-README-Template) - README structure
* [Shields.io](https://shields.io/) - README badges

<p align="right">(<a href="#readme-top">back to top</a>)</p>

<!-- MARKDOWN LINKS & IMAGES -->
[issues-shield]: https://img.shields.io/github/issues/sudoblark/sudoblark.ai.bookshelf-demo.svg?style=for-the-badge
[issues-url]: https://github.com/sudoblark/sudoblark.ai.bookshelf-demo/issues
[license-shield]: https://img.shields.io/github/license/sudoblark/sudoblark.ai.bookshelf-demo.svg?style=for-the-badge
[license-url]: https://github.com/sudoblark/sudoblark.ai.bookshelf-demo/blob/main/LICENSE.txt
[linkedin-shield]: https://img.shields.io/badge/-LinkedIn-black.svg?style=for-the-badge&logo=linkedin&colorB=555
[linkedin-url]: https://linkedin.com/company/sudoblark
[ci-shield]: https://github.com/sudoblark/sudoblark.ai.bookshelf-demo/actions/workflows/pull-request.yaml/badge.svg?style=for-the-badge
[ci-url]: https://github.com/sudoblark/sudoblark.ai.bookshelf-demo/actions/workflows/pull-request.yaml

<!-- Technology Badges -->
[Python-badge]: https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white
[Python-url]: https://www.python.org/
[AWS-badge]: https://img.shields.io/badge/AWS-232F3E?style=for-the-badge&logo=amazon-aws&logoColor=white
[AWS-url]: https://aws.amazon.com/
[Terraform-badge]: https://img.shields.io/badge/Terraform-7B42BC?style=for-the-badge&logo=terraform&logoColor=white
[Terraform-url]: https://www.terraform.io/
[GitHub-Actions-badge]: https://img.shields.io/badge/GitHub_Actions-2088FF?style=for-the-badge&logo=github-actions&logoColor=white
[GitHub-Actions-url]: https://github.com/features/actions
