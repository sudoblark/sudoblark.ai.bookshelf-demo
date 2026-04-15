FROM python:3.12-slim

RUN useradd --create-home --shell /bin/bash appuser

WORKDIR /app

COPY streaming-agent/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend directory (includes streaming-agent and common modules)
COPY --chown=appuser:appuser .. .

# Set PYTHONPATH so common module is importable
ENV PYTHONPATH=/app:$PYTHONPATH

WORKDIR /app/streaming-agent

USER appuser

EXPOSE 8000

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
