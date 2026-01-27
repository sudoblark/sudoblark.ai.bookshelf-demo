
# Demo Runbook — Facilitator Steps

This runbook is the authoritative checklist for running the Bookshelf demo during a workshop or conference. Follow the steps exactly for a predictable demo experience.

Prerequisites

- Python 3.8+
- git
- Flutter installed and on PATH (required to run the UI)
- A set of sample book cover images (JPG/PNG/WEBP)

Quick run (recommended)

1. Clone and install everything:

```bash
git clone https://github.com/sudoblark/sudoblark.ai.bookshelf-demo.git
cd sudoblark.ai.bookshelf-demo
make install-all
```

2. Open three terminals and run each component:

Terminal A — Processor (watch & extract):
```bash
make run-processor
```

Terminal B — Backend (REST API):
```bash
make run-backend
```

Terminal C — UI (Flutter client):
```bash
make run-ui
```

3. Upload a test image (or use the UI Upload tab):

```bash
curl -X POST -F "file=@/path/to/book-cover.jpg" http://localhost:5000/upload
```

4. Verify processing:

- Watch Processor logs (Terminal A) for file detection and extraction events.
- In the Flutter UI (Terminal C), open the Books tab — the processed record should appear shortly after processing completes.

5. Optional: Check backend endpoints:

```bash
curl http://localhost:5000/books
curl http://localhost:5000/status
```

6. Stop the demo: Ctrl+C in each terminal.

Notes and troubleshooting

- `make install-all` installs processor, backend, and UI dependencies. If Flutter isn't available the `make install-ui` step will fail — ensure Flutter is installed on the demo machine.
- To run the UI against a non-local backend host, run `flutter` inside `user_interface/` with:

```bash
cd user_interface
flutter run --dart-define=API_HOST=http://<backend-host>:5000
```

- If port 5000 is occupied, set the backend to another port and point the UI to it via `API_HOST`.

Advanced checks

- Confirm Parquet output:

```bash
ls -lh data/processed/
```

- Upload via curl and verify processor logs for extraction events.

This document is the single source of truth for demo execution.
make run-ui

