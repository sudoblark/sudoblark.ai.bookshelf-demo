
"""
Centralized configuration for the Bookshelf Demo backend API.

This module defines all configuration settings used by the Flask application,
including paths to data directories, allowed file types, and server parameters.

Configuration can be overridden via environment variables for different
deployment environments (development, testing, production).
"""

import os
from pathlib import Path


# ============================================================================
# Paths
# ============================================================================

# Compute paths relative to the project structure
# backend/settings.py -> backend/ -> project_root/
BACKEND_DIR = Path(__file__).parent.resolve()
PROJECT_ROOT = BACKEND_DIR.parent

# Data directories (shared with processor)
RAW_DIR = PROJECT_ROOT / "data" / "raw"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"

# Ensure directories exist
RAW_DIR.mkdir(parents=True, exist_ok=True)
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================================
# File Upload Settings
# ============================================================================

# Allowed file extensions for image uploads (lowercase)
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp'}

# Maximum file upload size (in bytes)
# Default: 50 MB
MAX_CONTENT_LENGTH = int(os.getenv('MAX_CONTENT_LENGTH', 50 * 1024 * 1024))


# ============================================================================
# Flask Configuration
# ============================================================================

# Flask secret key for session management
# In production, use a strong, random value from environment
SECRET_KEY = os.getenv(
    'FLASK_SECRET_KEY',
    'dev-secret-key-change-in-production'  # Development default only
)

# Flask debug mode
# Set to False in production
DEBUG = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'

# Flask host and port
FLASK_HOST = os.getenv('FLASK_HOST', '127.0.0.1')
FLASK_PORT = int(os.getenv('FLASK_PORT', 5000))

# Environment name (development, testing, production)
ENVIRONMENT = os.getenv('FLASK_ENV', 'development')


# ============================================================================
# Application Settings
# ============================================================================

# Parquet file naming pattern for reads
# The backend looks for the newest .parquet file in PROCESSED_DIR
PARQUET_EXTENSION = '.parquet'

# Safe filename length limit (to prevent excessively long filenames)
MAX_FILENAME_LENGTH = 255

# Temporary upload directory (for future use if needed)
TEMP_DIR = PROJECT_ROOT / "tmp"


def get_config_dict() -> dict:
    """
    Return all configuration as a dictionary.
    
    Useful for logging or debugging configuration values.
    
    Returns:
        Dictionary of configuration key-value pairs.
    """
    return {
        'RAW_DIR': str(RAW_DIR),
        'PROCESSED_DIR': str(PROCESSED_DIR),
        'ALLOWED_EXTENSIONS': ALLOWED_EXTENSIONS,
        'MAX_CONTENT_LENGTH': MAX_CONTENT_LENGTH,
        'DEBUG': DEBUG,
        'FLASK_HOST': FLASK_HOST,
        'FLASK_PORT': FLASK_PORT,
        'ENVIRONMENT': ENVIRONMENT,
    }


if __name__ == "__main__":
    # Display configuration when run directly
    import json
    print("Backend Configuration:")
    print(json.dumps(get_config_dict(), indent=2))
