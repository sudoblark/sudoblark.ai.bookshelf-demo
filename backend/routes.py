
"""
Flask routes for the Bookshelf Demo backend API.

Provides two main endpoints:
- POST /upload: Accept and save book cover images to data/raw/
- GET /books: Retrieve processed book metadata from Parquet files

Design:
- Thin endpoints focused on I/O only
- Delegates business logic to parquet_reader, utils, and settings
- Provides clear HTTP status codes and JSON responses
- Does not trigger extraction directly (processor watcher handles it)
"""

from flask import Blueprint, request, jsonify
from pathlib import Path

from logger import get_logger
from settings import RAW_DIR, PROCESSED_DIR, ALLOWED_EXTENSIONS
from utils import validate_filename_input, safe_filename
from parquet_reader import read_all_parquet, ParquetReadError, get_parquet_info

logger = get_logger(__name__)

# Create blueprint for routes
api = Blueprint('api', __name__)


# ============================================================================
# Routes
# ============================================================================

@api.route('/upload', methods=['POST'])
def upload_file():
    """
    Upload a book cover image.
    
    Accepts multipart/form-data with a file field.
    Validates the file extension and saves it to data/raw/.
    The processor watcher will automatically detect and process it.
    
    Returns:
        JSON response with status, filename, and path.
        HTTP 400 if validation fails.
        HTTP 500 if save fails.
    
    Example Request:
        curl -X POST -F "file=@cover.jpg" http://localhost:5001/upload
    
    Example Response (success):
        {
            "status": "ok",
            "message": "File uploaded successfully",
            "filename": "cover.jpg",
            "path": "/absolute/path/to/data/raw/cover.jpg"
        }
    
    Example Response (validation error):
        {
            "status": "error",
            "message": "File extension not allowed",
            "allowed_extensions": ["jpg", "jpeg", "png", "webp"]
        }
    """
    logger.debug("POST /upload request received")
    
    # Check if file is present in request
    if 'file' not in request.files:
        logger.warning("Upload request missing 'file' field")
        return jsonify({
            "status": "error",
            "message": "No file provided"
        }), 400
    
    file = request.files['file']
    
    # Check if file has a filename
    if file.filename == '':
        logger.warning("Upload request has empty filename")
        return jsonify({
            "status": "error",
            "message": "File has no name"
        }), 400
    
    # Validate filename and extension
    if not validate_filename_input(file.filename):
        logger.warning(f"Invalid file rejected: {file.filename}")
        return jsonify({
            "status": "error",
            "message": "File extension not allowed",
            "allowed_extensions": list(ALLOWED_EXTENSIONS)
        }), 400
    
    # Generate safe filename
    safe_name = safe_filename(file.filename)
    if not safe_name:
        logger.error(f"Failed to generate safe filename for: {file.filename}")
        return jsonify({
            "status": "error",
            "message": "Could not process filename"
        }), 400
    
    # Save file to raw directory
    try:
        filepath = RAW_DIR / safe_name
        file.save(str(filepath))
        
        logger.info(f"File uploaded successfully: {safe_name}")
        
        return jsonify({
            "status": "ok",
            "message": "File uploaded successfully",
            "filename": safe_name,
            "path": str(filepath)
        }), 200
    
    except Exception as e:
        logger.error(f"Failed to save uploaded file: {e}", exc_info=True)
        return jsonify({
            "status": "error",
            "message": "Failed to save file"
        }), 500


@api.route('/books', methods=['GET'])
def get_books():
    """
    Retrieve processed book metadata.
    
    Returns the records from the newest Parquet file in data/processed/.
    If no Parquet files exist yet, returns an empty list with a status message.
    
    Returns:
        JSON response with list of book records.
        HTTP 200 on success (even if no records yet).
        HTTP 500 if Parquet file exists but cannot be read.
    
    Example Request:
        curl http://localhost:5001/books
    
    Example Response (with data):
        {
            "status": "ok",
            "count": 3,
            "books": [
                {
                    "filename": "cover1.jpg",
                    "title": "Extracted Title",
                    "author": "Extracted Author",
                    "isbn": "Extracted ISBN",
                    "processed_at": "2026-01-26T12:34:56Z"
                },
                ...
            ]
        }
    
    Example Response (no data yet):
        {
            "status": "ok",
            "count": 0,
            "message": "No processed books yet. Upload images and wait for processing.",
            "books": []
        }
    """
    logger.debug("GET /books request received")
    
    try:
        # Read all Parquet files and aggregate records
        records = read_all_parquet()
        
        # Prepare response with metadata and books list (demo-friendly)
        response = {
            "status": "ok",
            "count": len(records),
            "books": records
        }

        # Add helpful message if no data yet
        if not records:
            response["message"] = "No processed books yet. Upload images and wait for processing."

        logger.info(f"Books endpoint returning {len(records)} records")

        return jsonify(response), 200
    
    except ParquetReadError as e:
        logger.error(f"Failed to read Parquet file: {e}")
        return jsonify({
            "status": "error",
            "message": "Failed to read processed data",
            "error": str(e)
        }), 500
    
    except Exception as e:
        logger.error(f"Unexpected error in /books endpoint: {e}", exc_info=True)
        return jsonify({
            "status": "error",
            "message": "An unexpected error occurred"
        }), 500


@api.route('/status', methods=['GET'])
def get_status():
    """
    Get the status of the system.
    
    Returns information about:
    - Number of images in data/raw/
    - Latest processed file information
    - Overall system status
    
    Returns:
        JSON response with system status information.
    
    Example Request:
        curl http://localhost:5001/status
    
    Example Response:
        {
            "status": "ok",
            "system": "healthy",
            "raw_images_pending": 0,
            "latest_processed_file": "output_20260126_120000.parquet",
            "processed_records": 5,
            "processed_columns": 8
        }
    """
    logger.debug("GET /status request received")
    
    try:
        # Count pending raw images
        raw_files = []
        if RAW_DIR.exists():
            raw_files = [f for f in RAW_DIR.iterdir() if f.is_file()]
        
        # Get latest processed file info
        latest_file, num_records, num_columns = get_parquet_info()
        
        response = {
            "status": "ok",
            "system": "healthy",
            "raw_images_pending": len(raw_files),
            "latest_processed_file": latest_file.split('/')[-1] if latest_file else None,
            "processed_records": num_records,
            "processed_columns": num_columns
        }
        
        logger.info(f"Status endpoint: {len(raw_files)} pending, {num_records} processed records")
        
        return jsonify(response), 200
    
    except Exception as e:
        logger.error(f"Error in /status endpoint: {e}", exc_info=True)
        return jsonify({
            "status": "error",
            "system": "unhealthy",
            "message": "Failed to retrieve system status"
        }), 500