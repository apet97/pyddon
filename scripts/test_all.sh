#!/bin/bash
# Test script for Clockify Add-ons
# Runs all tests for the repository

set -e

echo "🧪 Running Clockify Add-ons test suite..."

echo ""
echo "🔍 Running root tests (API Studio + Universal Webhook)..."
./venv/bin/python -m pytest tests/ -v --tb=short

echo ""
echo "🔍 Running Clockify Python Addon tests..."
cd clockify-python-addon
./venv/bin/python -m pytest tests/ -v --tb=short

echo ""
echo "✅ All tests completed successfully!"