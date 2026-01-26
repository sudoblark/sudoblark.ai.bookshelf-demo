
"""
Flask application entry point for the Bookshelf Demo backend API.

This module creates and configures the Flask app instance, registers routes,
and provides a runnable entry point for the backend server.

Responsibilities:
- Create and configure Flask app using settings.py
- Register routes/blueprints from routes.py
- Initialize logging
- Provide runnable entry point for `python app.py`

Constraints:
- Keep minimal (app setup only)
- No endpoint logic here (belongs in routes.py)
- No data processing or Parquet reading here
- Local-only demo (no auth, no database, no cloud)
"""

from flask import Flask, jsonify
from pathlib import Path

from logger import get_logger
from settings import (
    SECRET_KEY, DEBUG, FLASK_HOST, FLASK_PORT, ENVIRONMENT,
    MAX_CONTENT_LENGTH, get_config_dict
)
from routes import api

logger = get_logger(__name__)


def create_app():
    """
    Create and configure the Flask application.
    
    Returns:
        Configured Flask app instance.
    """
    # Create Flask app
    app = Flask(__name__)
    
    # Configure app from settings
    app.config['SECRET_KEY'] = SECRET_KEY
    app.config['DEBUG'] = DEBUG
    app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH
    app.config['ENV'] = ENVIRONMENT
    
    logger.info(f"Flask app created for {ENVIRONMENT} environment")
    
    # Register blueprints/routes
    app.register_blueprint(api)
    logger.debug("API routes registered")
    
    # Add error handlers
    @app.errorhandler(404)
    def not_found(error):
        """Handle 404 Not Found errors."""
        logger.warning(f"404 Not Found: {error}")
        return jsonify({
            "status": "error",
            "message": "Endpoint not found",
            "path": error.description
        }), 404
    
    @app.errorhandler(405)
    def method_not_allowed(error):
        """Handle 405 Method Not Allowed errors."""
        logger.warning(f"405 Method Not Allowed: {error}")
        return jsonify({
            "status": "error",
            "message": "Method not allowed for this endpoint"
        }), 405
    
    @app.errorhandler(500)
    def internal_error(error):
        """Handle 500 Internal Server Error."""
        logger.error(f"500 Internal Server Error: {error}", exc_info=True)
        return jsonify({
            "status": "error",
            "message": "Internal server error"
        }), 500
    
    # Add health check endpoint
    @app.route('/health', methods=['GET'])
    def health_check():
        """Simple health check endpoint."""
        logger.debug("Health check requested")
        return jsonify({
            "status": "healthy",
            "service": "Bookshelf Demo Backend",
            "environment": ENVIRONMENT
        }), 200
    
    # Add configuration info endpoint (debug only)
    if DEBUG:
        @app.route('/config', methods=['GET'])
        def show_config():
            """Display configuration (debug mode only)."""
            logger.debug("Configuration info requested")
            return jsonify({
                "status": "ok",
                "environment": ENVIRONMENT,
                "config": get_config_dict()
            }), 200
    
    logger.info("Flask app configured successfully")
    
    return app


def main():
    """
    Main entry point for running the Flask server.
    
    Creates the app and runs it on the configured host and port.
    """
    logger.info("=" * 60)
    logger.info("Bookshelf Demo Backend API")
    logger.info("=" * 60)
    
    try:
        # Create app
        app = create_app()
        
        # Display server info
        logger.info(f"Starting server on {FLASK_HOST}:{FLASK_PORT}")
        logger.info(f"Environment: {ENVIRONMENT}")
        if DEBUG:
            logger.warning("DEBUG mode is enabled")
        
        # Run Flask development server
        # Note: For production, use a WSGI server like gunicorn
        app.run(
            host=FLASK_HOST,
            port=FLASK_PORT,
            debug=DEBUG,
            use_reloader=DEBUG
        )
    
    except Exception as e:
        logger.error(f"Failed to start server: {e}", exc_info=True)
        raise


if __name__ == '__main__':
    main()
