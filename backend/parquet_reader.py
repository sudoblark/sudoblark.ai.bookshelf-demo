
# Copilot: Flask routes for the local demo backend.
#
# Endpoints required:
# - POST /upload
#   - Accept multipart/form-data with a single file field named "file".
#   - Save the file into RAW_DIR (defined in settings.py) using a safe filename.
#   - Validate allowed extensions (jpg, jpeg, png).
#   - Return JSON response: { "status": "ok", "filename": "...", "path": "..." }.
#
# - GET /books
#   - Read the newest parquet file from PROCESSED_DIR via parquet_reader.py.
#   - Return JSON array of book records (list[dict]).
#   - If none exists yet, return an empty list and a helpful status message.
#
# Constraints:
# - Keep endpoints thin: perform I/O only.
# - Do not trigger extraction directly; the processor watcher handles it.
# - Provide clear HTTP status codes and JSON error messages.
# - Keep code demo-friendly and readable; avoid over-engineering.