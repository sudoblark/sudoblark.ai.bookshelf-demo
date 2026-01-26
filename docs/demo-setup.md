# Demo Setup Guide

This guide walks you through setting up and running a complete end-to-end demo of the Bookshelf system.

## Prerequisites

- Python 3.8+
- `make` command available
- A few sample book cover images (JPG, PNG, or WEBP)

## Quick Demo (5 minutes)

### 1. Install Everything

```bash
cd /path/to/sudoblark.ai.bookshelf-demo
make install-all
```

### 2. Start Components in Separate Terminals

**Terminal 1 (Processor):**
```bash
make run-processor
```

**Terminal 2 (Backend):**
```bash
make run-backend
```

Arrange the terminals side-by-side to see both logs at once.

### 3. Upload a Test Image

In a new terminal:

```bash
curl -X POST -F "file=@/path/to/book-cover.jpg" http://localhost:5000/upload
```

Response:
```json
{
  "status": "success",
  "filename": "book-cover.jpg",
  "path": "data/raw/book-cover.jpg"
}
```

### 4. Retrieve Processed Data

```bash
curl http://localhost:5000/books
```

Response (JSON array with extracted metadata):
```json
[
  {
    "filename": "book-cover.jpg",
    "title": "Extracted Title",
    "author": "Extracted Author",
    "isbn": "Extracted ISBN",
    "processed_at": "2026-01-26T12:34:56Z"
  }
]
```

### 5. Check System Status

```bash
curl http://localhost:5000/status
```

Shows count of pending images and processed records.

## Detailed Walkthrough

### Setup Phase

1. **Clone the repository**
   ```bash
   git clone https://github.com/sudoblark/sudoblark.ai.bookshelf-demo.git
   cd sudoblark.ai.bookshelf-demo
   ```

2. **Install all dependencies**
   ```bash
   make install-all
   ```
   This creates isolated virtual environments for processor and backend.

3. **Prepare test images**
   ```bash
   mkdir -p data/raw
   cp ~/Pictures/book-covers/*.jpg data/raw/
   ```

### Demo Phase - Run Both Components in Separate Terminals

**Terminal 1 - Processor:**
```bash
make run-processor
```

**Terminal 2 - Backend:**
```bash
make run-backend
```

Arrange terminals side-by-side to watch for:
- **Processor logs:** File detection and extraction events
- **Backend logs:** HTTP request handling

### Demo Phase - Upload and Process

In a new terminal, upload a test image:

```bash
curl -X POST -F "file=@data/raw/sample.jpg" http://localhost:5000/upload
```

Watch the processor logs—you'll see:
1. File detected in `data/raw/`
2. Metadata extracted
3. Parquet file written to `data/processed/`

### Demo Phase - Retrieve Results

Fetch all processed records:
```bash
curl http://localhost:5000/books
```

System status:
```bash
curl http://localhost:5000/status
```

Health check:
```bash
curl http://localhost:5000/health
```

## Running Components Separately

For easier debugging, run in separate terminals:

**Terminal 1 - Processor:**
```bash
make run-processor
```

**Terminal 2 - Backend:**
```bash
make run-backend
```

## Batch Upload Demo

Upload multiple images at once:

```bash
for img in data/raw/*.jpg; do
  echo "Uploading: $img"
  curl -X POST -F "file=@$img" http://localhost:5000/upload
  sleep 1  # Brief pause between uploads
done
```

Then retrieve all results:
```bash
curl http://localhost:5000/books
```

## Viewing Output Files

Processed data is stored as Parquet files:

```bash
ls -lh data/processed/
```

Files are named: `output_YYYYMMDD_HHMMSS.parquet`

## Stopping the Demo

Press **Ctrl+C** in each terminal (processor and backend) to stop them.

## Cleanup

Reset everything:

```bash
make clean
make install-all
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Port 5000 already in use | `FLASK_PORT=5001 make run-backend` |
| Processor not detecting files | Check `processor/processor.log` |
| Files not processing | Verify file extensions (jpg, png, webp) |
| Permission errors | Ensure `data/` directory is writable |
| Virtual env errors | Run `make clean` then `make install-all` |

## Next Steps for Extended Demo

- Show processor logs in real-time
- Demonstrate error handling with invalid files
- Show `/status` endpoint updating as files process
- Display the Parquet output files
- Preview future Copilot Studio integration points
