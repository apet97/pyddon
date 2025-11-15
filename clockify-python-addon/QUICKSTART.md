# Clockify Python Addon - Quick Start Guide

Get your Clockify addon up and running in 5 minutes!

## Prerequisites

- Python 3.11 or higher
- pip or poetry
- A Clockify workspace (free or paid)

## Step 1: Installation

```bash
# Clone or download this repository
cd clockify-python-addon

# Create virtual environment
python3.11 -m venv venv

# Activate virtual environment
# On macOS/Linux:
source venv/bin/activate
# On Windows:
# venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

## Step 2: Configuration

```bash
# Copy environment template
cp .env.example .env

# Edit .env file
nano .env  # or use your preferred editor
```

**Minimum required settings:**

```env
BASE_URL=http://localhost:8000
DEBUG=true
REQUIRE_SIGNATURE_VERIFICATION=false
```

For production, set your actual domain:

```env
BASE_URL=https://your-addon-domain.com
DEBUG=false
REQUIRE_SIGNATURE_VERIFICATION=true
```

## Step 3: Database Setup

```bash
# Initialize database
alembic upgrade head
```

This creates the SQLite database with all required tables.

## Step 4: Start the Server

```bash
# Start development server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

You should see:
```
INFO:     Uvicorn running on http://0.0.0.0:8000
INFO:     Application starting...
```

## Step 5: Verify Installation

Open your browser and visit:

- **Health Check**: http://localhost:8000/health
- **Manifest**: http://localhost:8000/manifest
- **API UI**: http://localhost:8000/ui

You should see the API Studio interface!

## Step 6: Install in Clockify (Development)

### Option A: Using ngrok (Recommended for testing)

```bash
# Install ngrok: https://ngrok.com/download

# Start ngrok tunnel
ngrok http 8000

# Copy the HTTPS URL (e.g., https://abc123.ngrok.io)
# Update .env:
BASE_URL=https://abc123.ngrok.io

# Restart the server
```

### Option B: Deploy to a server

Deploy to Heroku, DigitalOcean, AWS, or any hosting provider that supports Python.

### Install the Addon

1. Go to Clockify Developer Portal: https://developer.clockify.me
2. Create a new developer account (if you don't have one)
3. Click "Create Addon"
4. Enter your manifest URL: `https://your-domain.com/manifest`
5. Click "Install" in your test workspace

## Step 7: Test the Addon

1. Open Clockify workspace
2. Look for "API Studio" in the sidebar
3. Click it to open the addon UI
4. Try making an API call:
   - Method: GET
   - Endpoint: `/v1/workspaces/{workspaceId}/projects`
   - Fill in your workspace ID
   - Click "Execute API Call"

You should see a list of projects!

## Common Commands

```bash
# Run tests
PYTHONPATH=. pytest tests/ -v

# Run tests with coverage
pytest --cov=app --cov-report=html

# View coverage report
open htmlcov/index.html

# Create database migration
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head

# Rollback migration
alembic downgrade -1

# Format code (if using black)
black app/ tests/

# Type checking (if using mypy)
mypy app/
```

## Using Docker

```bash
# Build and start with Docker Compose
docker-compose up --build

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

## Troubleshooting

### Port already in use
```bash
# Kill process on port 8000
lsof -ti:8000 | xargs kill -9

# Or use a different port
uvicorn app.main:app --port 8001
```

### Database errors
```bash
# Reset database
rm clockify_addon.db
alembic upgrade head
```

### Module not found
```bash
# Ensure virtual environment is activated
source venv/bin/activate

# Reinstall dependencies
pip install -r requirements.txt
```

### JWT verification fails
```bash
# For development, disable verification
# In .env:
REQUIRE_SIGNATURE_VERIFICATION=false
```

## Next Steps

- **Customize the manifest**: Edit `app/manifest.py` to add/remove permissions
- **Add webhook handlers**: Extend `app/webhook_router.py`
- **Customize UI**: Modify `static/index.html` and `static/styles.css`
- **Add business logic**: Create new modules in `app/`
- **Deploy to production**: See deployment guide in README.md

## Getting Help

- **Clockify API Docs**: https://docs.clockify.me
- **Developer Portal**: https://developer.clockify.me
- **Community Forum**: https://forum.clockify.me

## What's Included

✅ Full lifecycle management (install, update, delete)
✅ Webhook receivers for all Clockify events
✅ No-code API caller with OpenAPI validation
✅ Automatic workspace bootstrap on install
✅ Rate limiting (50 RPS)
✅ Token verification with developer bypass
✅ Structured logging
✅ Complete test suite
✅ Database migrations
✅ Production-ready architecture

Enjoy building with Clockify! 🚀
