.PHONY: help install-processor install-backend install-all run-processor run-backend clean

help:
	@echo "Sudoblark AI Bookshelf Demo - Make Targets"
	@echo "=========================================="
	@echo ""
	@echo "Setup Targets:"
	@echo "  make install-processor    Install processor dependencies in isolated venv"
	@echo "  make install-backend      Install backend dependencies in isolated venv"
	@echo "  make install-all          Install both processor and backend"
	@echo ""
	@echo "Run Targets:"
	@echo "  make run-processor        Run processor (filesystem monitoring)"
	@echo "  make run-backend          Run backend REST API on http://localhost:5001"
	@echo ""
	@echo "Maintenance:"
	@echo "  make clean                Remove venvs and logs"
	@echo "  make help                 Show this help message"
	@echo ""
	@echo "Examples:"
	@echo "  make install-all"
	@echo "  make run-processor        # in terminal 1"
	@echo "  make run-backend          # in terminal 2"

# Install processor in isolated virtual environment
install-processor:
	@echo "Installing processor dependencies..."
	@cd processor && \
	  python3 -m venv venv && \
	  . venv/bin/activate && \
	  pip install --upgrade pip setuptools && \
	  pip install -r requirements.txt && \
	  echo "✓ Processor installed to processor/venv"

# Install backend in isolated virtual environment
install-backend:
	@echo "Installing backend dependencies..."
	@cd backend && \
	  python3 -m venv venv && \
	  . venv/bin/activate && \
	  pip install --upgrade pip setuptools && \
	  pip install -r requirements.txt && \
	  echo "✓ Backend installed to backend/venv"

# Install both processor and backend
install-all: install-processor install-backend
	@echo "✓ All dependencies installed"

# Run processor only
run-processor:
	@echo "Starting processor (monitoring data/raw/ for new images)..."
	@echo "Press Ctrl+C to stop"
	@cd processor && \
	  . venv/bin/activate && \
	  python main.py

# Run backend only
run-backend:
	@echo "Starting REST API backend on http://localhost:5001"
	@echo "Available endpoints:"
	@echo "  POST /upload              - Upload image files"
	@echo "  GET  /books               - Get processed books"
	@echo "  GET  /status              - Get system status"
	@echo "  GET  /health              - Health check"
	@echo ""
	@echo "Press Ctrl+C to stop"
	@cd backend && \
	  . venv/bin/activate && \
	  python app.py


# Clean up virtual environments and logs
clean:
	@echo "Cleaning up virtual environments and logs..."
	@rm -rf processor/venv backend/venv
	@rm -f processor/processor.log backend/backend.log
	@echo "✓ Cleanup complete"
