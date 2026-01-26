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

<p align="right">(<a href="#readme-top">back to top</a>)</p>

## Getting Started

Follow these steps to set up and run the processor locally.

### Prerequisites

- Python 3.8 or higher
- pip (Python package manager)

### Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/sudoblark/sudoblark.ai.bookshelf-demo.git
   cd sudoblark.ai.bookshelf-demo
   ```

2. Navigate to the processor directory:
   ```bash
   cd processor
   ```

3. Create a Python virtual environment:
   ```bash
   python3 -m venv venv
   ```

4. Activate the virtual environment:
   ```bash
   # On macOS and Linux:
   source venv/bin/activate
   
   # On Windows:
   venv\Scripts\activate
   ```

5. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

<p align="right">(<a href="#readme-top">back to top</a>)</p>

## Usage

### Running the Processor

Start the event-driven processor:

```bash
python main.py
```

The processor will:
1. Watch the `data/raw/` directory for new image files
2. Extract metadata from each image as it arrives
3. Write the structured metadata to Parquet files in `data/processed/`

### Adding Images

Simply place book cover images into the `data/raw/` directory:

```bash
cp /path/to/book-cover.jpg data/raw/
```

Supported formats: PNG, JPG, JPEG, WEBP

The processor automatically detects new files and begins processing immediately.

### Output

Processed data is written to `data/processed/` as timestamped Parquet files containing:
- Book metadata extracted from cover images
- Structured fields optimized for querying and analysis
- Processing timestamps for tracking and auditing

<p align="right">(<a href="#readme-top">back to top</a>)</p>

## Documentation

For a detailed understanding of how the system is designed and how each component works, see the [Architecture Guide](docs/architecture.md).

The architecture document includes:
- System overview and data flow diagrams
- Component responsibilities and design patterns
- Module dependencies and interactions
- Future enhancement roadmap
- Error handling strategies

<p align="right">(<a href="#readme-top">back to top</a>)</p>

## 
## Project Structure

```
sudoblark.ai.bookshelf-demo/
├── processor/              # Core ETL pipeline
│   ├── main.py            # Entry point and orchestration
│   ├── watcher.py         # Filesystem event monitoring
│   ├── extractor.py       # Metadata extraction logic
│   ├── parquet_writer.py  # Parquet file generation
│   ├── utils.py           # Utility functions
│   └── requirements.txt    # Python dependencies
├── data/
│   ├── raw/               # Input directory for book cover images
│   └── processed/         # Output directory for Parquet files
├── docs/                  # Documentation
└── README.md              # This file
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
