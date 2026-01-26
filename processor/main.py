
# Copilot: This is the entrypoint for the local ETL pipeline.
# Start the filesystem watcher, receive new image events,
# route images through the extractor, then write Parquet output.
# Keep logic simple and delegate responsibilities to watcher.py,
# extractor.py, and parquet_writer.py.
