# Deployment Guide

Complete guide for deploying Clockify add-ons to development, staging, and production environments.

---

## Prerequisites

- **Docker** 24+ and **Docker Compose** 2+
- **PostgreSQL** 14+ (for production)
- **Git**
- **Domain name** with SSL certificate (for production)
- **Python 3.11+** (for local development without Docker)

---

## Quick Start (Local Development)

### 1. Clone and Setup

```bash
git clone <repository-url>
cd pyddon

# Copy environment template
cp .env.example .env

# Edit .env with your settings
# For local dev, you can use the defaults (SQLite databases)
nano .env
```

### 2. Start All Services

```bash
# Build and start all services
docker-compose up -d

# View logs
docker-compose logs -f

# View specific service logs
docker-compose logs -f api_studio
docker-compose logs -f universal_webhook
docker-compose logs -f clockify_addon
```

### 3. Verify Deployment

```bash
# Check all containers are running
docker-compose ps

# Health checks
curl http://localhost:8000/ready  # API Studio
curl http://localhost:8001/ready  # Universal Webhook
curl http://localhost:8002/health # Clockify Addon

# Metrics endpoints
curl http://localhost:8000/metrics
curl http://localhost:8001/metrics
curl http://localhost:8002/metrics
```

### 4. Stop Services

```bash
# Stop all services
docker-compose down

# Stop and remove volumes (CAUTION: deletes data)
docker-compose down -v
```

---

## Production Deployment (VPS/Cloud)

### Step 1: Server Setup

```bash
# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh

# Install Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/download/v2.23.0/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Verify installation
docker --version
docker-compose --version

# Create deployment directory
sudo mkdir -p /opt/clockify-addons
sudo chown $USER:$USER /opt/clockify-addons
cd /opt/clockify-addons
```

### Step 2: Clone Repository

```bash
git clone <repository-url> .

# Or if using a specific branch/tag
git clone -b main <repository-url> .
```

### Step 3: Configure Environment

```bash
# Copy environment template
cp .env.example .env

# Generate a strong PostgreSQL password
openssl rand -base64 32

# Edit production configuration
nano .env
```

**Critical variables to set:**

```bash
# PostgreSQL (REQUIRED)
POSTGRES_PASSWORD=<generated-strong-password>

# API Studio
API_STUDIO_DB_URL=postgresql+asyncpg://clockify:<password>@postgres:5432/api_studio
API_STUDIO_REQUIRE_SIGNATURE_VERIFICATION=true

# Universal Webhook
UNIVERSAL_WEBHOOK_DB_URL=postgresql+asyncpg://clockify:<password>@postgres:5432/universal_webhook
UNIVERSAL_WEBHOOK_REQUIRE_SIGNATURE_VERIFICATION=true

# Clockify Addon
DATABASE_URL=postgresql+asyncpg://clockify:<password>@postgres:5432/clockify_addon
REQUIRE_SIGNATURE_VERIFICATION=true
DEBUG=false

# Shared
LOG_LEVEL=INFO
```

### Step 4: Build and Start Services

```bash
# Build Docker images
docker-compose build

# Start services in detached mode
docker-compose up -d

# Watch startup logs
docker-compose logs -f
```

### Step 5: Verify Deployment

```bash
# Check all containers are healthy
docker-compose ps

# Should show:
# clockify-postgres          Up (healthy)
# clockify-api-studio        Up (healthy)
# clockify-universal-webhook Up (healthy)
# clockify-addon             Up (healthy)

# Test health endpoints
curl http://localhost:8000/ready
curl http://localhost:8001/ready
curl http://localhost:8002/health

# Check database
docker-compose exec postgres psql -U clockify -l
# Should list: api_studio, universal_webhook, clockify_addon
```

### Step 6: Configure Reverse Proxy (Nginx)

Install Nginx:
```bash
sudo apt update
sudo apt install nginx certbot python3-certbot-nginx -y
```

Create site configuration:
```bash
sudo nano /etc/nginx/sites-available/clockify-addons
```

**Configuration:**
```nginx
# API Studio
server {
    listen 443 ssl http2;
    server_name api-studio.yourdomain.com;

    ssl_certificate /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Request-ID $request_id;
    }
}

# Universal Webhook
server {
    listen 443 ssl http2;
    server_name universal-webhook.yourdomain.com;

    ssl_certificate /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;

    location / {
        proxy_pass http://localhost:8001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Request-ID $request_id;
    }
}

# Clockify Addon
server {
    listen 443 ssl http2;
    server_name clockify-addon.yourdomain.com;

    ssl_certificate /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;

    location / {
        proxy_pass http://localhost:8002;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Request-ID $request_id;
    }
}
```

Enable site and reload:
```bash
# Enable site
sudo ln -s /etc/nginx/sites-available/clockify-addons /etc/nginx/sites-enabled/

# Test configuration
sudo nginx -t

# Reload Nginx
sudo systemctl reload nginx

# Get SSL certificates
sudo certbot --nginx -d api-studio.yourdomain.com -d universal-webhook.yourdomain.com -d clockify-addon.yourdomain.com
```

---

## Database Management

### Running Migrations Manually

```bash
# Run all migrations
./scripts/run_migrations.sh

# Or run individually:

# API Studio
docker-compose exec api_studio sh -c "DATABASE_URL=\$API_STUDIO_DB_URL alembic upgrade head"

# Universal Webhook
docker-compose exec universal_webhook sh -c "DATABASE_URL=\$UNIVERSAL_WEBHOOK_DB_URL alembic upgrade head"

# Clockify Addon
docker-compose exec clockify_addon alembic upgrade head
```

### Creating New Migrations

```bash
# API Studio
docker-compose exec api_studio sh -c "DATABASE_URL=\$API_STUDIO_DB_URL alembic revision --autogenerate -m 'description'"

# Universal Webhook
docker-compose exec universal_webhook sh -c "DATABASE_URL=\$UNIVERSAL_WEBHOOK_DB_URL alembic revision --autogenerate -m 'description'"

# Clockify Addon
docker-compose exec clockify_addon alembic revision --autogenerate -m "description"
```

### Database Backup

```bash
# Backup all databases
docker-compose exec postgres pg_dumpall -U clockify > backup_$(date +%Y%m%d_%H%M%S).sql

# Backup specific database
docker-compose exec postgres pg_dump -U clockify api_studio > api_studio_backup.sql

# Automated daily backups (cron)
echo "0 2 * * * cd /opt/clockify-addons && docker-compose exec -T postgres pg_dumpall -U clockify > /backups/clockify_\$(date +\%Y\%m\%d).sql" | crontab -
```

### Database Restore

```bash
# Restore all databases
cat backup_20250129.sql | docker-compose exec -T postgres psql -U clockify

# Restore specific database
cat api_studio_backup.sql | docker-compose exec -T postgres psql -U clockify -d api_studio
```

---

## Monitoring & Observability

### Prometheus Setup

Create `prometheus.yml`:
```yaml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'api-studio'
    static_configs:
      - targets: ['localhost:8000']
    metrics_path: '/metrics'

  - job_name: 'universal-webhook'
    static_configs:
      - targets: ['localhost:8001']
    metrics_path: '/metrics'

  - job_name: 'clockify-addon'
    static_configs:
      - targets: ['localhost:8002']
    metrics_path: '/metrics'
```

Start Prometheus:
```bash
docker run -d \
  --name prometheus \
  --network pyddon_clockify-network \
  -p 9090:9090 \
  -v $(pwd)/prometheus.yml:/etc/prometheus/prometheus.yml \
  prom/prometheus
```

Access Prometheus: http://localhost:9090

### Log Aggregation

View logs:
```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f api_studio

# Last 100 lines
docker-compose logs --tail=100

# Export logs to file
docker-compose logs --no-color > logs_$(date +%Y%m%d).txt
```

Ship logs to external service (e.g., Datadog):
```bash
# Add to docker-compose.yml under each service
logging:
  driver: "json-file"
  options:
    max-size: "10m"
    max-file: "3"
    labels: "service,environment"
```

---

## Troubleshooting

### Service Won't Start

```bash
# Check container status
docker-compose ps

# Check logs for errors
docker-compose logs <service-name>

# Restart specific service
docker-compose restart <service-name>

# Rebuild and restart
docker-compose up -d --no-deps --build <service-name>
```

### Database Connection Issues

```bash
# Check PostgreSQL is running
docker-compose ps postgres

# Check databases exist
docker-compose exec postgres psql -U clockify -l

# Test connection manually
docker-compose exec postgres psql -U clockify -d api_studio -c "SELECT 1"

# Check connection string in .env
grep DB_URL .env
```

### Migration Errors

```bash
# Check current migration version
docker-compose exec api_studio sh -c "DATABASE_URL=\$API_STUDIO_DB_URL alembic current"

# View migration history
docker-compose exec api_studio sh -c "DATABASE_URL=\$API_STUDIO_DB_URL alembic history"

# Downgrade one version
docker-compose exec api_studio sh -c "DATABASE_URL=\$API_STUDIO_DB_URL alembic downgrade -1"

# Re-run upgrade
docker-compose exec api_studio sh -c "DATABASE_URL=\$API_STUDIO_DB_URL alembic upgrade head"
```

### Health Check Failures

```bash
# Manual health check
curl -v http://localhost:8000/ready

# Check database connectivity
docker-compose exec api_studio python -c "
from api_studio.db import engine
import asyncio
asyncio.run(engine.connect())
print('DB Connected!')
"
```

---

## Updates & Rollbacks

### Update to Latest Version

```bash
# Pull latest code
git fetch origin
git pull origin main

# Rebuild images
docker-compose build

# Stop services
docker-compose down

# Run migrations
./scripts/run_migrations.sh

# Start services
docker-compose up -d

# Verify
docker-compose ps
docker-compose logs --tail=50
```

### Rollback to Previous Version

```bash
# Stop services
docker-compose down

# Restore previous version
git log --oneline  # Find commit hash
git checkout <previous-commit>

# Rebuild
docker-compose build

# Downgrade migrations if needed
docker-compose run --rm api_studio sh -c "DATABASE_URL=\$API_STUDIO_DB_URL alembic downgrade <revision>"

# Start services
docker-compose up -d

# Verify
curl http://localhost:8000/ready
```

---

## Security Checklist

### Production Deployment

- [ ] Change default PostgreSQL password (`POSTGRES_PASSWORD`)
- [ ] Enable signature verification (`REQUIRE_SIGNATURE_VERIFICATION=true`)
- [ ] Use HTTPS with valid SSL certificate
- [ ] Configure firewall (allow only ports 443, 22)
- [ ] Set up log rotation
- [ ] Enable automatic security updates
- [ ] Regular database backups (daily recommended)
- [ ] Monitor metrics and logs
- [ ] Keep Docker images updated
- [ ] Use strong passwords in .env
- [ ] Restrict SSH access (key-based authentication only)
- [ ] Configure rate limiting on reverse proxy

### Environment File Security

```bash
# Secure .env file
chmod 600 .env
chown $USER:$USER .env

# Never commit .env to version control
echo ".env" >> .gitignore
```

---

## Performance Tuning

### Database Connection Pooling

Not needed for async drivers (asyncpg, aiosqlite use connection pooling automatically).

### Worker Scaling

For high traffic, use Gunicorn with multiple workers:

```bash
# Add to docker-compose.yml CMD
gunicorn api_studio.main:app \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000
```

### Log Retention

Reduce retention days if database grows too large:

```bash
# In .env
API_STUDIO_WEBHOOK_LOG_RETENTION_DAYS=30
UW_FLOW_EXECUTION_RETENTION_DAYS=30
```

---

## Support & Resources

- **Architecture:** [ARCHITECTURE.md](ARCHITECTURE.md)
- **Environment Variables:** [ENV_VARS_REFERENCE.md](ENV_VARS_REFERENCE.md)
- **Quickstart:** [QUICKSTART.md](QUICKSTART.md)
- **API Documentation:** `http://localhost:8000/docs` (FastAPI Swagger UI)
- **Clockify Developer Portal:** https://developer.clockify.me
- **Clockify API Docs:** https://docs.clockify.me

---

**Last Updated:** 2025-01-29
**Version:** 1.0.0
