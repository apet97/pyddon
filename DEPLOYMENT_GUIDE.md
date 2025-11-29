# Updated Deployment Guide

This guide provides comprehensive instructions for deploying the Clockify add-ons in development, staging, and production environments.

## Architecture Overview

This repository contains **three production-ready Clockify add-ons**:

1. **API Studio** - STANDARD tier support (Port 8000)
2. **Universal Webhook** - ENTERPRISE tier with advanced features (Port 8001)
3. **Clockify Python Addon** - Production reference implementation (Port 8002)

All services share a common PostgreSQL database instance with 3 separate databases and use shared infrastructure components from `/clockify_core/`.

## Database Migration Strategy

The repository uses a hybrid migration approach:

- **API Studio and Universal Webhook**: Share a single alembic configuration in `/alembic/`
- **Clockify Python Addon**: Has its own alembic configuration in `/clockify-python-addon/alembic/`

### Running Migrations

**Docker Compose (Recommended)**: Migrations are automatically run when services start via the `CMD` instruction in the Dockerfiles.

**Manual Migration Commands**:

```bash
# For API Studio and Universal Webhook (from project root):
docker-compose exec api_studio sh -c "DATABASE_URL=\$API_STUDIO_DB_URL alembic upgrade head"
docker-compose exec universal_webhook sh -c "DATABASE_URL=\$UNIVERSAL_WEBHOOK_DB_URL alembic upgrade head"

# For Clockify Python Addon (from clockify-python-addon directory):
docker-compose -f ./clockify-python-addon/docker-compose.yml exec clockify_addon alembic upgrade head
```

## Development Environment Setup

### 1. Clone and Configure

```bash
git clone <repository-url>
cd pyddon
cp .env.example .env
```

Edit `.env` to customize settings if needed. Development defaults use SQLite databases.

### 2. Build and Run

```bash
# Build and start all services
docker-compose up -d --build

# View logs
docker-compose logs -f
```

### 3. Verify Deployment

```bash
# Check all services are running
docker-compose ps

# Test health endpoints
curl http://localhost:8000/healthz  # API Studio
curl http://localhost:8001/healthz  # Universal Webhook
curl http://localhost:8002/health   # Clockify Addon

# Check metrics
curl http://localhost:8000/metrics
curl http://localhost:8001/metrics
curl http://localhost:8002/metrics
```

## Production Deployment

### Environment Configuration

Update the following in your `.env` file:

```bash
# Generate strong password: openssl rand -base64 32
POSTGRES_PASSWORD=your_strong_password_here

# Database URLs (use PostgreSQL for production)
API_STUDIO_DB_URL=postgresql+asyncpg://clockify:your_password@postgres:5432/api_studio
UNIVERSAL_WEBHOOK_DB_URL=postgresql+asyncpg://clockify:your_password@postgres:5432/universal_webhook
DATABASE_URL=postgresql+asyncpg://clockify:your_password@postgres:5432/clockify_addon

# Security settings (CRITICAL: Must be true in production)
API_STUDIO_REQUIRE_SIGNATURE_VERIFICATION=true
UNIVERSAL_WEBHOOK_REQUIRE_SIGNATURE_VERIFICATION=true
REQUIRE_SIGNATURE_VERIFICATION=true

# Production settings
DEBUG=false
LOG_LEVEL=INFO
CLOCKIFY_ADDON_BASE_URL=https://your-domain.com
```

### Security Considerations

1. **Signature Verification**: Enable signature verification for all services to prevent unauthorized webhook calls
2. **Base URL**: Set proper public domain for Clockify to register webhooks
3. **Database Security**: Use strong passwords and network isolation
4. **Firewall**: Only allow necessary ports (443 for web, 22 for SSH)
5. **Regular Updates**: Keep Docker images and dependencies updated

### Docker Compose Production Setup

```bash
# Build production images
docker-compose build

# Start services
docker-compose up -d

# Verify deployment
docker-compose ps
docker-compose logs --tail=50
```

## Monitoring and Observability

### Metrics

All services expose Prometheus-compatible metrics at `/metrics`:

- `addon_uptime_seconds` - Service uptime
- `webhooks_received_total` - Webhook counter (by event type)
- `flows_executed_total` - Flow execution counter
- `api_calls_total` - API call counter

### Health Checks

- **Liveness**: `/healthz` - Is the process alive?
- **Readiness**: `/ready` - Is the service ready to handle traffic?
- Both endpoints check database connectivity

### Logging

Services use structured logging with configurable log levels. Log files are stored in the `logs/` directory in each service's respective subdirectory.

## Testing

### Running Tests

```bash
# Run all tests (from project root)
./scripts/test_all.sh

# Run root tests (API Studio + Universal Webhook)
PYTHONPATH=. pytest tests/ -v

# Run Clockify Python Addon tests
cd clockify-python-addon
PYTHONPATH=. pytest tests/ -v
```

### Docker-based Testing

```bash
# Run tests in isolated environment
docker-compose -f docker-compose.test.yml run --rm test-runner
```

## Troubleshooting

### Common Issues

1. **Database Connection Failures**: Verify `POSTGRES_PASSWORD` matches in all database URLs
2. **Health Check Failures**: Check PostgreSQL is healthy and accessible
3. **Migration Failures**: Ensure proper database permissions and connection strings
4. **Signature Verification**: In development, you may disable for testing but must enable in production

### Service Recovery

```bash
# Restart specific service
docker-compose restart api_studio

# Restart with rebuild
docker-compose up -d --force-recreate api_studio

# Check container logs
docker-compose logs api_studio
```

## Backup and Recovery

### Database Backup

```bash
# Full backup of all databases
docker-compose exec postgres pg_dumpall -U clockify > backup_$(date +%Y%m%d).sql

# Individual database backup
docker-compose exec postgres pg_dump -U clockify api_studio > api_studio_backup.sql
```

### Backup Automation

Add to crontab for automated backups:

```bash
# Daily backup at 2 AM
0 2 * * * cd /opt/clockify-addons && docker-compose exec -T postgres pg_dumpall -U clockify > /backups/clockify_$(date +\%Y\%m\%d).sql
```

## Performance Considerations

### Rate Limiting

- Default: 50 RPS per workspace (token bucket algorithm)
- Configurable via `RATE_LIMIT_RPS` environment variable
- Per-workspace isolation prevents cross-tenant abuse

### Bootstrap Configuration

- `BOOTSTRAP_MAX_RPS`: Limit bootstrap requests per second (default: 25)
- `BOOTSTRAP_MAX_PAGES`: Maximum pages per endpoint (default: 1000/200)
- `BOOTSTRAP_BATCH_SIZE`: Items processed per batch (default: 10)

### Data Retention

Services automatically clean up old records based on retention settings:
- Webhook logs: 90 days (configurable)
- Flow executions: 30-90 days (configurable)
- Entity cache: 7 days (configurable)

## Security Hardening

1. **Non-root containers**: All services run as non-root user `clockify`
2. **Multi-stage builds**: Minimal attack surface with only necessary dependencies
3. **Input validation**: Pydantic models enforce schema validation
4. **Signature verification**: Clockify webhook signatures are verified
5. **Domain allowlisting**: Only approved Clockify domains allowed
6. **Payload limits**: 1MB API calls, 5MB webhooks (configurable)

## Production Checklist

- [ ] Generate strong PostgreSQL password (`openssl rand -base64 32`)
- [ ] Configure production database URLs
- [ ] Enable signature verification for all services
- [ ] Set DEBUG=false
- [ ] Configure SSL/TLS with reverse proxy
- [ ] Set up monitoring and alerting
- [ ] Configure automated backups
- [ ] Set up log aggregation
- [ ] Test disaster recovery procedures
- [ ] Review retention settings for storage capacity

## Scaling Considerations

For high-traffic environments:

1. **Vertical Scaling**: Increase container resources (CPU/RAM)
2. **Horizontal Scaling**: Add container replicas behind load balancer
3. **Database Scaling**: Consider PostgreSQL read replicas
4. **Caching**: Enable Redis for distributed caching (optional)
5. **Monitoring**: Set up Prometheus/Grafana for performance metrics