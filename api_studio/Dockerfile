# Multi-stage Dockerfile for API Studio
# Production-ready containerization with security hardening

FROM python:3.11.8-slim-bookworm AS builder

# Python optimization flags
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install build dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        build-essential \
        && rm -rf /var/lib/apt/lists/*

# Copy only requirements first for better caching
COPY pyproject.toml ./

# Build wheels for all dependencies
RUN pip install --upgrade pip setuptools wheel && \
    pip wheel --wheel-dir /tmp/wheels -e .

# Runtime stage
FROM python:3.11.8-slim-bookworm AS runtime

# Python optimization flags
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app

WORKDIR /app

# Install runtime dependencies (curl for health checks)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        curl \
        && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN addgroup --system clockify && \
    adduser --system --ingroup clockify clockify

# Copy and install wheels from builder
COPY --from=builder /tmp/wheels /tmp/wheels
RUN pip install --upgrade pip && \
    pip install --no-cache-dir /tmp/wheels/* && \
    rm -rf /tmp/wheels

# Copy application code
COPY . .

# Create logs directory and set ownership
RUN mkdir -p logs && \
    chown -R clockify:clockify /app

# Switch to non-root user
USER clockify

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/healthz || exit 1

# Run migrations and start application
CMD ["/bin/sh", "-c", "alembic upgrade head && uvicorn api_studio.main:app --host 0.0.0.0 --port 8000"]
