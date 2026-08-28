#!/usr/bin/env bash
# ==============================================================================
# Vertex Construction & PCCC - Production Startup Script (Linux / Cloud Server)
# ==============================================================================

set -e

echo "Starting Vertex Construction & PCCC Quote Automation in Production..."

# Export Python path
export PYTHONPATH="${PYTHONPATH}:."
export PYTHONUNBUFFERED=1

# Check .env file
if [ ! -f ".env" ]; then
    echo "Warning: .env file not found. Copying .env.example..."
    cp .env.example .env
fi

# Run with Gunicorn + Uvicorn Worker
WORKERS=${WEB_CONCURRENCY:-4}
PORT=${PORT:-8000}
HOST=${HOST:-0.0.0.0}

echo "Launching Gunicorn with ${WORKERS} Uvicorn workers on ${HOST}:${PORT}..."
exec gunicorn -w "${WORKERS}" \
    -k uvicorn.workers.UvicornWorker \
    -b "${HOST}:${PORT}" \
    --timeout 120 \
    --keep-alive 5 \
    --access-logfile - \
    --error-logfile - \
    main:app
