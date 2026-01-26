
# Copilot: Small shared helpers for the backend.
#
# Suggested helpers:
# - is_allowed_file(filename): bool using settings.ALLOWED_EXTENSIONS
# - safe_filename(filename): strip path parts and normalise
# - list_parquet_files(processed_dir): list[str]
# - newest_file(paths): choose by modification time
#
# Constraints:
# - Keep helpers small and side-effect free.
# - No Flask dependencies here unless strictly necessary.
