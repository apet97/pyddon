# Clockify Python Addon - Quick Reference

## 🚀 Quick Start

```bash
# Setup
cd clockify-python-addon
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Configure
cp .env.example .env
# Edit .env with your settings

# Database
alembic upgrade head

# Run Development
uvicorn app.main:app --reload --port 8000

# Run Tests
PYTHONPATH=. pytest tests/ -v

# Run with Coverage
pytest tests/ --cov=app --cov-report=html
```

## 📁 Key Files

| File | Purpose |
|------|---------|
| `app/token_verification.py` | RS256 JWT verification |
| `app/lifecycle.py` | Lifecycle event handlers |
| `app/webhook_router.py` | Webhook event handlers |
| `app/api_caller.py` | No-code API executor |
| `app/bootstrap.py` | Workspace data bootstrap |
| `manifest.json` | Addon configuration |
| `.env` | Environment configuration |

## 🔑 Environment Variables (Critical)

```bash
# Security (REQUIRED in production)
REQUIRE_SIGNATURE_VERIFICATION=true
CLOCKIFY_JWKS_URL=https://developer.clockify.me/.well-known/jwks.json

# Server
BASE_URL=https://your-addon.com
DEBUG=false

# Database
DATABASE_URL=postgresql+asyncpg://user:pass@host/db

# Rate Limiting
RATE_LIMIT_RPS=50
```

See `ENV_VARS.md` for complete reference.

## 🧪 Test Commands

```bash
# All tests
PYTHONPATH=. pytest tests/ -v

# Specific suite
PYTHONPATH=. pytest tests/test_security.py -v

# With coverage
PYTHONPATH=. pytest tests/ --cov=app --cov-report=term-missing

# Generate HTML report
PYTHONPATH=. pytest tests/ --cov=app --cov-report=html
# Open htmlcov/index.html
```

## 🔒 Security Features

✅ **RS256 JWT Verification** - Full JWKS-based verification  
✅ **Workspace Isolation** - Claims validated against payloads  
✅ **Addon ID Validation** - Ensures requests are for this addon  
✅ **Rate Limiting** - 50 RPS per workspace (configurable)  
✅ **Deduplication** - DB-backed, survives restarts  
✅ **No Token Leakage** - Tokens never logged  

## 🎯 Key Endpoints

| Endpoint | Purpose |
|----------|---------|
| `GET /health` | Health check |
| `GET /ready` | Readiness probe |
| `GET /metrics` | Prometheus counters |
| `GET /manifest` | Addon manifest |
| `POST /lifecycle/installed` | Installation handler |
| `POST /lifecycle/settings-updated` | Settings update |
| `POST /lifecycle/deleted` | Uninstall handler |
| `POST /webhooks/*` | Webhook receivers |
| `GET /ui/api-explorer/endpoints` | List operations |
| `POST /ui/api-explorer/execute` | Execute an operation |
| `POST /api-call` | No-code API executor |
| `GET /ui` | Addon UI |

## 📊 Project Stats

- **Tests:** 49 (100% passing)
- **Coverage:** 40%
- **Webhook Events:** 50
- **Permission Scopes:** 19
- **Documentation:** 18KB

## 🐛 Common Issues

### JWT Verification Fails
```bash
# Check JWKS URL is accessible
curl https://developer.clockify.me/.well-known/jwks.json

# Enable developer mode for testing
REQUIRE_SIGNATURE_VERIFICATION=false
```

### Database Connection Error
```bash
# Verify DATABASE_URL format
# SQLite: sqlite+aiosqlite:///./clockify_addon.db
# PostgreSQL: postgresql+asyncpg://user:pass@host/db

# Run migrations
alembic upgrade head
```

### Port Already in Use
```bash
# Use different port
uvicorn app.main:app --port 8001

# Or kill existing process
lsof -ti:8000 | xargs kill -9
```

## 📚 Documentation

- `IMPLEMENTATION_COMPLETE.md` - Final completion report
- `HARDENING_SUMMARY.md` - Detailed implementation breakdown
- `MARKETPLACE_NOTES.md` - Marketplace reviewer guide
- `ENV_VARS.md` - Environment variable reference
- `QUICKSTART.md` - Getting started guide
- `README.md` - Architecture and features

## 🚀 Deployment Checklist

**Before Production:**
- [ ] Set `REQUIRE_SIGNATURE_VERIFICATION=true`
- [ ] Use PostgreSQL (not SQLite)
- [ ] Set `DEBUG=false`
- [ ] Configure proper `BASE_URL` with HTTPS
- [ ] Update `manifest.json` with production URLs
- [ ] Confirm `CLOCKIFY_JWKS_URL` (or `CLOCKIFY_ENVIRONMENT`) points to the correct Clockify JWKS host
- [ ] Enable Redis (`USE_REDIS=true`)
- [ ] Configure log aggregation
- [ ] Set up monitoring
- [ ] Run `alembic upgrade head`
- [ ] Run full test suite
- [ ] Load test rate limiting

**Marketplace Submission:**
- [ ] Update vendor information in `manifest.json`
- [ ] Add privacy policy URL
- [ ] Add terms of service URL
- [ ] Add support email
- [ ] Review all 50 webhook subscriptions
- [ ] Review all 19 permission scopes
- [ ] Test installation flow
- [ ] Test uninstall flow
- [ ] Verify all endpoints respond correctly

## 🎓 Key Concepts

### JWT Verification Flow
1. Extract JWT from the canonical `Clockify-Signature` header (legacy `X-Addon-Signature` still accepted)
2. Fetch JWKS from Clockify (cached 1 hour)
3. Find public key by `kid` from JWT header
4. Verify RS256 signature
5. Validate claims (iss, sub, workspaceId, addonId)
6. Enforce workspace and addon ID match

### Deduplication Strategy
1. Check memory cache (fast O(1) lookup)
2. Check database (persistent, survives restarts)
3. Store in both if not found
4. Graceful degradation on DB errors

### Rate Limiting
- Token bucket algorithm
- 50 requests per second per workspace
- Configurable via `RATE_LIMIT_RPS`
- Graceful blocking (waits, doesn't reject)
- Redis support for distributed systems

## 💡 Tips

**Development:**
- Use SQLite and disable verification for speed
- Set `LOG_LEVEL=DEBUG` for detailed logs
- Use `--reload` flag with uvicorn
- Keep `AUTO_BOOTSTRAP_ON_INSTALL=false` for testing

**Production:**
- Use PostgreSQL for reliability
- Enable Redis for multi-instance deployments
- Use structured JSON logs (`LOG_FORMAT=json`)
- Monitor `/health` endpoint
- Set up log aggregation (ELK, Datadog, etc.)

**Testing:**
- Run tests before commits
- Check coverage regularly
- Mock external HTTP calls
- Use in-memory DB for tests

## 🔗 Useful Links

- Clockify Developer Portal: https://developer.clockify.me
- Clockify API Docs: https://docs.clockify.me
- Addon Guide: https://developer.clockify.me/addons
- JWKS Endpoint: https://developer.clockify.me/.well-known/jwks.json

---

**Status:** ✅ Production Ready  
**Last Updated:** November 14, 2024
