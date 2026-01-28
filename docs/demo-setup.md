
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

Open the `user_interface/` folder in VS Code, choose an emulator or physical device from the device selector, then press Run/Debug to start the app. Add `--dart-define=API_HOST=http://<backend-host>:5001` to your launch configuration if you need to point the UI at a non-local backend.

Note: Use `flutter emulators` to view a list of available emulators, and run a new emulator as required. i.e. `flutter emulators --launch Medium_Phone_API_36.1`. You can also just run `flutter run`
in the `user_interface` folder to load the app onto the emulated device.

3. Upload a test image (or use the UI Upload tab):

```bash
curl -X POST -F "file=@/path/to/book-cover.jpg" http://localhost:5001/upload
```

4. Verify processing:

- Watch Processor logs (Terminal A) for file detection and extraction events.
- In the Flutter UI (Terminal C), open the Books tab — the processed record should appear shortly after processing completes.

5. Optional: Check backend endpoints:

```bash
curl http://localhost:5001/books
curl http://localhost:5001/status
```

6. Stop the demo: Ctrl+C in each terminal.

Notes and troubleshooting

- `make install-all` installs processor, backend, and UI dependencies. If Flutter isn't available the `make install-ui` step will fail — ensure Flutter is installed on the demo machine.
- To run the UI against a non-local backend host, run `flutter` inside `user_interface/` with:

```bash
cd user_interface
flutter run --dart-define=API_HOST=http://<backend-host>:5001
```

- If the default backend port is occupied, run the backend on another port and point the UI to it via `API_HOST`.

Advanced checks

- Confirm Parquet output:

```bash
ls -lh data/processed/
```

- Upload via curl and verify processor logs for extraction events.

This document is the single source of truth for demo execution.

