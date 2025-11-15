FROM python:3.11.8-slim-bookworm AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --upgrade pip setuptools wheel \
    && pip wheel --wheel-dir /tmp/wheels -r requirements.txt


FROM python:3.11.8-slim-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN addgroup --system clockify && adduser --system --ingroup clockify clockify

COPY --from=builder /tmp/wheels /tmp/wheels
RUN pip install --upgrade pip \
    && pip install --no-cache-dir /tmp/wheels/* \
    && rm -rf /tmp/wheels

COPY . .
RUN mkdir -p logs && chown -R clockify:clockify /app

USER clockify

EXPOSE 8000

CMD ["/bin/sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
