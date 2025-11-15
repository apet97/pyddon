# Deployment Guide - Production-Ready Clockify Add-ons

This guide covers deploying the hardened Clockify API Studio and Universal Webhook add-ons to production.

---

## Prerequisites

- Python 3.11+
- PostgreSQL 14+ (production database)
- Prometheus (for metrics scraping)
- Log aggregation system (e.g., ELK, Datadog, Splunk)

---

## Quick Start (Local Development)

```bash
# 1. Clone repository
cd clockify-api-studio-py-kit

# 2. Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -e .

# 4. Run database migrations
alembic upgrade head

# 5. Start API Studio
uvicorn api_studio.main:app --host 0.0.0.0 --port 8000 --reload

# 6. Start Universal Webhook (in another terminal)
source venv/bin/activate
uvicorn universal_webhook.main:app --host 0.0.0.0 --port 8001 --reload

# 7. Verify health
curl http://localhost:8000/healthz
curl http://localhost:8001/healthz

# 8. Check metrics
curl http://localhost:8000/metrics
curl http://localhost:8001/metrics
```

---

## Production Deployment

### 1. Environment Configuration

Create `.env` file or set environment variables:

#### API Studio
```bash
# Server
APP_PORT=8000

# Database (PostgreSQL recommended)
API_STUDIO_DB_URL=postgresql+asyncpg://username:password@db-host:5432/api_studio

# Clockify API
CLOCKIFY_API_BASE_URL=https://api.clockify.me

# Bootstrap
API_STUDIO_BOOTSTRAP_MAX_RPS=25
API_STUDIO_BOOTSTRAP_INCLUDE_HEAVY_ENDPOINTS=false

# Data Retention
API_STUDIO_WEBHOOK_LOG_RETENTION_DAYS=90
API_STUDIO_FLOW_EXECUTION_RETENTION_DAYS=30
```

#### Universal Webhook
```bash
# Server
UNIVERSAL_WEBHOOK_PORT=8001

# Database (PostgreSQL recommended)
UNIVERSAL_WEBHOOK_DB_URL=postgresql+asyncpg://username:password@db-host:5432/universal_webhook

# Bootstrap
UW_BOOTSTRAP_MAX_RPS=25
UW_BOOTSTRAP_INCLUDE_HEAVY=false
UW_BOOTSTRAP_INCLUDE_TIME_ENTRIES=false
UW_BOOTSTRAP_TIME_ENTRY_DAYS=30

# Webhooks
UW_ENABLE_CUSTOM_WEBHOOKS=true

# Flows
UW_ENABLE_FLOWS=true
UW_ENABLE_GENERIC_HTTP_ACTIONS=false

# Data Retention
UW_WEBHOOK_LOG_RETENTION_DAYS=90
UW_FLOW_EXECUTION_RETENTION_DAYS=30
UW_CACHE_TTL_DAYS=7
```

### 2. Database Setup

```bash
# Create databases
createdb api_studio
createdb universal_webhook

# Run migrations
export API_STUDIO_DB_URL=postgresql+asyncpg://user:pass@host/api_studio
alembic upgrade head

# For Universal Webhook, use its own migrations
export UNIVERSAL_WEBHOOK_DB_URL=postgresql+asyncpg://user:pass@host/universal_webhook
alembic upgrade head
```

### 3. Application Startup

#### Using Uvicorn (Development/Small Scale)
```bash
# API Studio
uvicorn api_studio.main:app \
  --host 0.0.0.0 \
  --port 8000 \
  --workers 4 \
  --log-config logging.conf

# Universal Webhook
uvicorn universal_webhook.main:app \
  --host 0.0.0.0 \
  --port 8001 \
  --workers 4 \
  --log-config logging.conf
```

#### Using Gunicorn (Production)
```bash
# API Studio
gunicorn api_studio.main:app \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000 \
  --log-level info \
  --access-logfile - \
  --error-logfile -

# Universal Webhook
gunicorn universal_webhook.main:app \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8001 \
  --log-level info
```

### 4. Docker Deployment

Create `Dockerfile`:
```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY pyproject.toml .
RUN pip install --no-cache-dir -e .

# Copy application code
COPY . .

# Run migrations on startup
RUN alembic upgrade head

# Expose ports
EXPOSE 8000 8001

# Start application
CMD ["uvicorn", "api_studio.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

`docker-compose.yml`:
```yaml
version: '3.8'

services:
  postgres:
    image: postgres:14
    environment:
      POSTGRES_USER: clockify
      POSTGRES_PASSWORD: ${DB_PASSWORD}
      POSTGRES_DB: clockify
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"

  api_studio:
    build: .
    environment:
      API_STUDIO_DB_URL: postgresql+asyncpg://clockify:${DB_PASSWORD}@postgres/clockify
      API_STUDIO_WEBHOOK_LOG_RETENTION_DAYS: 90
      API_STUDIO_FLOW_EXECUTION_RETENTION_DAYS: 30
    ports:
      - "8000:8000"
    depends_on:
      - postgres
    command: uvicorn api_studio.main:app --host 0.0.0.0 --port 8000

  universal_webhook:
    build: .
    environment:
      UNIVERSAL_WEBHOOK_DB_URL: postgresql+asyncpg://clockify:${DB_PASSWORD}@postgres/clockify
      UW_WEBHOOK_LOG_RETENTION_DAYS: 90
      UW_FLOW_EXECUTION_RETENTION_DAYS: 30
    ports:
      - "8001:8001"
    depends_on:
      - postgres
    command: uvicorn universal_webhook.main:app --host 0.0.0.0 --port 8001

  prometheus:
    image: prom/prometheus:latest
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
      - prometheus_data:/prometheus
    ports:
      - "9090:9090"
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'

volumes:
  postgres_data:
  prometheus_data:
```

### 5. Kubernetes Deployment

`deployment.yaml`:
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: api-studio
spec:
  replicas: 3
  selector:
    matchLabels:
      app: api-studio
  template:
    metadata:
      labels:
        app: api-studio
    spec:
      containers:
      - name: api-studio
        image: your-registry/api-studio:latest
        ports:
        - containerPort: 8000
        env:
        - name: API_STUDIO_DB_URL
          valueFrom:
            secretKeyRef:
              name: db-secret
              key: url
        livenessProbe:
          httpGet:
            path: /healthz
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /healthz
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 5
---
apiVersion: v1
kind: Service
metadata:
  name: api-studio
spec:
  selector:
    app: api-studio
  ports:
  - port: 80
    targetPort: 8000
  type: LoadBalancer
```

---

## Monitoring Setup

### 1. Prometheus Configuration

`prometheus.yml`:
```yaml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'api-studio'
    static_configs:
      - targets: ['api-studio:8000']
    metrics_path: '/metrics'

  - job_name: 'universal-webhook'
    static_configs:
      - targets: ['universal-webhook:8001']
    metrics_path: '/metrics'
```

### 2. Grafana Dashboard

Key metrics to monitor:
- `addon_uptime_seconds` - Service uptime
- `webhooks_received_total` - Total webhooks received
- `webhooks_errors_*` - Error counters
- `flows_executed_total` - Total flow executions
- `flows_executed_failed` - Failed flow executions
- `lifecycle_installed_total` - Installation count

Sample queries:
```promql
# Webhook rate
rate(webhooks_received_total[5m])

# Error rate
rate(webhooks_errors_total[5m])

# Flow success rate
rate(flows_executed_completed[5m]) / rate(flows_executed_total[5m])
```

### 3. Alerting Rules

`alerts.yml`:
```yaml
groups:
  - name: clockify_addons
    rules:
      - alert: HighErrorRate
        expr: rate(webhooks_errors_total[5m]) > 0.1
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High webhook error rate"

      - alert: ServiceDown
        expr: up{job="api-studio"} == 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "API Studio service is down"

      - alert: DatabaseUnhealthy
        expr: addon_healthcheck_database_status != 1
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "Database connectivity issue"
```

### 4. Logging Configuration

`logging.conf`:
```ini
[loggers]
keys=root,api_studio,universal_webhook

[handlers]
keys=console,file

[formatters]
keys=json

[logger_root]
level=INFO
handlers=console,file

[logger_api_studio]
level=INFO
handlers=console,file
qualname=api_studio
propagate=0

[logger_universal_webhook]
level=INFO
handlers=console,file
qualname=universal_webhook
propagate=0

[handler_console]
class=StreamHandler
level=INFO
formatter=json
args=(sys.stdout,)

[handler_file]
class=logging.handlers.RotatingFileHandler
level=INFO
formatter=json
args=('logs/addon.log', 'a', 10485760, 5)

[formatter_json]
format={"time":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s","message":"%(message)s"}
datefmt=%Y-%m-%dT%H:%M:%S
```

---

## Health Checks

### Endpoint
```bash
GET /healthz
```

### Expected Response (Healthy)
```json
{
  "status": "ok",
  "database": "ok",
  "service": "api-studio"
}
```

### Expected Response (Degraded)
```json
{
  "status": "degraded",
  "database": "error: connection refused",
  "service": "api-studio"
}
```

### Kubernetes Probes
```yaml
livenessProbe:
  httpGet:
    path: /healthz
    port: 8000
  initialDelaySeconds: 30
  periodSeconds: 10
  timeoutSeconds: 5
  failureThreshold: 3

readinessProbe:
  httpGet:
    path: /healthz
    port: 8000
  initialDelaySeconds: 5
  periodSeconds: 5
  timeoutSeconds: 3
  failureThreshold: 2
```

---

## Security Checklist

- [ ] Use PostgreSQL with SSL/TLS
- [ ] Store secrets in secure vault (HashiCorp Vault, AWS Secrets Manager)
- [ ] Enable HTTPS/TLS for all endpoints
- [ ] Configure firewall rules (allow only Clockify IPs)
- [ ] Set up log aggregation with sensitive data redaction
- [ ] Enable audit logging
- [ ] Regular security updates
- [ ] Database backups (automated, encrypted)
- [ ] Disaster recovery plan
- [ ] Rate limiting at load balancer level

---

## Performance Tuning

### Database Connection Pool
```python
# In config.py
engine = create_async_engine(
    settings.db_url,
    pool_size=20,
    max_overflow=10,
    pool_pre_ping=True,
    pool_recycle=3600
)
```

### Worker Scaling
- Start with 4 workers per service
- Scale based on CPU usage (target: 70-80%)
- Use async workers (uvicorn.workers.UvicornWorker)

### Resource Limits (Kubernetes)
```yaml
resources:
  requests:
    memory: "512Mi"
    cpu: "500m"
  limits:
    memory: "1Gi"
    cpu: "1000m"
```

---

## Troubleshooting

### High Memory Usage
- Check retention settings (reduce days if needed)
- Verify cleanup task is running
- Check for webhook flood (implement rate limiting at gateway)

### Database Connection Issues
- Verify connection pool settings
- Check network connectivity
- Ensure PostgreSQL max_connections is sufficient

### Webhook Delays
- Check `/metrics` for error rates
- Verify Clockify API rate limits
- Review flow execution times

### Missing Metrics
- Verify Prometheus can reach `/metrics` endpoint
- Check firewall rules
- Ensure app started successfully

---

## Rollback Procedure

1. **Stop new version**
```bash
kubectl rollout undo deployment/api-studio
```

2. **Verify health**
```bash
curl https://api-studio.example.com/healthz
```

3. **Check logs**
```bash
kubectl logs -f deployment/api-studio
```

4. **Database rollback (if needed)**
```bash
alembic downgrade -1
```

---

## Support & Maintenance

### Daily Tasks
- Monitor health dashboard
- Check error rates in metrics
- Review critical alerts

### Weekly Tasks
- Review log aggregation for patterns
- Check database size and cleanup effectiveness
- Update dependencies (security patches)

### Monthly Tasks
- Performance review and optimization
- Capacity planning
- Security audit

---

## Testing Production Deployment

```bash
# 1. Health check
curl https://api-studio.example.com/healthz

# 2. Metrics
curl https://api-studio.example.com/metrics

# 3. Manifest
curl https://api-studio.example.com/manifest

# 4. Simulate installation
curl -X POST https://api-studio.example.com/lifecycle/installed \
  -H "Content-Type: application/json" \
  -d '{
    "addonId": "test-addon",
    "authToken": "test-token",
    "workspaceId": "test-workspace",
    "apiUrl": "https://api.clockify.me"
  }'

# 5. Send test webhook
curl -X POST https://api-studio.example.com/webhooks/clockify \
  -H "Content-Type: application/json" \
  -H "clockify-webhook-event-type: NEW_TIME_ENTRY" \
  -H "clockify-webhook-workspace-id: test-workspace" \
  -d '{
    "id": "test-entry",
    "workspaceId": "test-workspace"
  }'
```

---

**Deployment Status**: Ready for production
**Last Updated**: November 14, 2024
