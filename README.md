# Bookshelf Demo

<!-- PROJECT SHIELDS -->
[![License][license-shield]][license-url]

<!-- PROJECT LOGO -->
<br />
<div align="center">
  <h3 align="center">Bookshelf Demo</h3>

  <p align="center">
    A fully local, offline-friendly AI ETL pipeline for processing book cover images and extracting metadata into Parquet format.
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
    <li>
      <a href="#about-the-project">About The Project</a>
      <ul>
        <li><a href="#built-with">Built With</a></li>
      </ul>
    </li>
    <li>
      <a href="#getting-started">Getting Started</a>
      <ul>
        <li><a href="#prerequisites">Prerequisites</a></li>
        <li><a href="#installation">Installation</a></li>
      </ul>
    </li>
    <li><a href="#usage">Usage</a></li>
    <li><a href="#documentation">Documentation</a></li>
    <li><a href="#project-structure">Project Structure</a></li>
    <li><a href="#license">License</a></li>
  </ol>
</details>

## About The Project

The Bookshelf Demo is a fully local, offline-friendly ETL pipeline designed to:

- Monitor the `data/raw/` directory for new book cover images in real-time
- Extract book metadata using a local metadata extractor
- Generate structured Parquet files in `data/processed/` for analysis and machine learning workflows

This project is built with simplicity and local execution in mind—no cloud dependencies, no external APIs required by default.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

### Built With

* [![Python][Python]][Python-url]
* [![Pandas][Pandas]][Pandas-url]
* [![PyArrow][PyArrow]][PyArrow-url]
* [![Watchdog][Watchdog]][Watchdog-url]
* [![Flask][Flask]][Flask-url]

<p align="right">(<a href="#readme-top">back to top</a>)</p>

## Getting Started

### Prerequisites

- Python 3.8 or higher
- git

### Quick Start

1. Clone the repository:
   ```bash
   git clone https://github.com/sudoblark/sudoblark.ai.bookshelf-demo.git
   cd sudoblark.ai.bookshelf-demo
   ```

2. Install dependencies with Make:
   ```bash
   make install-all
   ```

3. Run processor and backend in separate terminals:
   
   **Terminal 1 (Processor):**
   ```bash
   make run-processor
   ```
   
   **Terminal 2 (Backend):**
   ```bash
   make run-backend
   ```

Both processes will log output to their respective terminals so you can monitor them side-by-side.

### Alternative: Processor Only

```bash
make install-processor
make run-processor
```

### See All Options

```bash
make help
```

<p align="right">(<a href="#readme-top">back to top</a>)</p>

## Usage

The processor automatically monitors `data/raw/` for new images, extracts metadata, and writes results to `data/processed/` as Parquet files.

**Processor:** `make run-processor`

**Backend API:** `make run-backend` (starts Flask on `http://localhost:5000`)

**Both together:** `make run-all`

### REST API Endpoints (Backend)

For detailed endpoint documentation and architecture overview, see [docs/architecture.md](docs/architecture.md).

Quick reference:
- `POST /upload` - Upload image files
- `GET /books` - Retrieve processed metadata
- `GET /status` - System status
- `GET /health` - Health check

### Adding Images

**Direct:** Drop images into `data/raw/`

**Via API:**
```bash
curl -X POST -F "file=@cover.jpg" http://localhost:5000/upload
```

Supported formats: PNG, JPG, JPEG, WEBP

<p align="right">(<a href="#readme-top">back to top</a>)</p>

## Documentation

For system architecture, design principles, and detailed data flow, see the [Architecture Guide](docs/architecture.md).

<p align="right">(<a href="#readme-top">back to top</a>)</p>

## 
## Project Structure

```
sudoblark.ai.bookshelf-demo/
├── processor/              # Core ETL pipeline
│   ├── main.py            # Entry point
│   ├── watcher.py         # Filesystem monitoring
│   ├── extractor.py       # Metadata extraction
│   ├── parquet_writer.py  # Parquet generation
│   ├── logger.py          # Logging
│   ├── requirements.txt    # Dependencies
│   └── venv/              # Virtual environment (local)
├── backend/               # Optional REST API
│   ├── app.py            # Flask server
│   ├── routes.py         # API endpoints
│   ├── parquet_reader.py # Parquet reading
│   ├── settings.py       # Configuration
│   ├── utils.py          # Utilities
│   ├── requirements.txt   # Dependencies
│   └── venv/             # Virtual environment (local)
├── data/
│   ├── raw/              # Input images
│   └── processed/        # Output Parquet files
├── docs/
│   └── architecture.md   # Architecture guide
├── Makefile              # Build automation
└── README.md             # This file
```

<p align="right">(<a href="#readme-top">back to top</a>)</p>

## License

Distributed under the MIT License. See `LICENSE.txt` for more information.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

<!-- MARKDOWN LINKS & IMAGES -->
[license-shield]: https://img.shields.io/badge/license-MIT-green.svg?style=for-the-badge
[license-url]: https://github.com/sudoblark/sudoblark.ai.bookshelf-demo/blob/main/LICENSE.txt
[Python]: https://img.shields.io/badge/Python-3.8+-blue?style=for-the-badge&logo=python
[Python-url]: https://www.python.org/
[Pandas]: https://img.shields.io/badge/Pandas-1.0+-black?style=for-the-badge&logo=pandas
[Pandas-url]: https://pandas.pydata.org/
[PyArrow]: https://img.shields.io/badge/PyArrow-Latest-orange?style=for-the-badge
[PyArrow-url]: https://arrow.apache.org/docs/python/
[Watchdog]: https://img.shields.io/badge/Watchdog-Latest-purple?style=for-the-badge
[Watchdog-url]: https://github.com/gorakhargosh/watchdog
[Flask]: https://img.shields.io/badge/Flask-2.0+-black?style=for-the-badge&logo=flask
[Flask-url]: https://flask.palletsprojects.com/
