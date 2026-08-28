# ==============================================================================
# Production Dockerfile for Vertex Construction & PCCC Quote Automation System
# Security Hardened: Non-Root User, Lean Size, Multi-Worker ASGI Architecture
# ==============================================================================

FROM python:3.10-slim AS base

# Prevent Python from writing .pyc files and buffer stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONIOENCODING=utf-8 \
    PORT=8000 \
    HOST=0.0.0.0 \
    APP_ENV=production

WORKDIR /app

# Install security updates and curl for healthchecks
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    gcc \
    libffi-dev \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application source code
COPY . .

# Create non-root user for security compliance
RUN groupadd -g 1000 vertexgroup && \
    useradd -u 1000 -g vertexgroup -m -s /bin/bash vertexuser && \
    mkdir -p /app/storage/uploads /app/storage/quotes /app/storage/templates /app/storage/reference_gdrive /app/data && \
    chown -R vertexuser:vertexgroup /app

# Switch to non-root user
USER vertexuser

# Expose Web Port
EXPOSE 8000

# Docker Healthcheck (checks dynamic PORT or 8000)
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -f http://127.0.0.1:${PORT:-8000}/api/health || exit 1

# Default Command: Multi-worker execution (reads PORT env dynamically)
CMD ["python", "run.py", "--host", "0.0.0.0"]

