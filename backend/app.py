
# Copilot: Flask application entrypoint for the local demo backend.
#
# Responsibilities:
# - Create the Flask app instance and configure it using settings.py.
# - Register routes/blueprints from routes.py.
# - Provide a single runnable entrypoint for `python app.py`.
#
# Constraints:
# - Keep this file minimal (app setup only).
# - Do not implement endpoint logic here (belongs in routes.py).
# - Do not implement parquet reading or file processing here.
# - Local-only demo: no auth, no database, no cloud.
#
# Runtime expectations:
# - The server runs on localhost and serves the Flutter app.
# - Upload endpoint saves images into ../data/raw/ for the processor to pick up.
