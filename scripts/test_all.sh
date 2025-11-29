#!/bin/bash
# Run all tests for all services
# This script executes the full test suite before deployment

set -e

echo "========================================="
echo "Running All Tests"
echo "========================================="

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Test results
TESTS_PASSED=0
TESTS_FAILED=0

# Root tests (api_studio + universal_webhook)
echo ""
echo -e "${BLUE}1. Running root tests (api_studio + universal_webhook)...${NC}"
if PYTHONPATH=. pytest tests/ -v --tb=short; then
    echo -e "${GREEN}✓ Root tests passed${NC}"
    ((TESTS_PASSED++))
else
    echo -e "${RED}✗ Root tests failed${NC}"
    ((TESTS_FAILED++))
fi

# Clockify-python-addon tests
echo ""
echo -e "${BLUE}2. Running clockify-python-addon tests...${NC}"
cd clockify-python-addon
if PYTHONPATH=. pytest tests/ -v --tb=short; then
    echo -e "${GREEN}✓ Clockify addon tests passed${NC}"
    ((TESTS_PASSED++))
else
    echo -e "${RED}✗ Clockify addon tests failed${NC}"
    ((TESTS_FAILED++))
fi
cd ..

# Summary
echo ""
echo "========================================="
echo "Test Summary"
echo "========================================="
echo -e "Passed: ${GREEN}${TESTS_PASSED}/2${NC}"
echo -e "Failed: ${RED}${TESTS_FAILED}/2${NC}"
echo "========================================="

if [ $TESTS_FAILED -gt 0 ]; then
    echo -e "${RED}Some tests failed. Please fix before deploying.${NC}"
    exit 1
else
    echo -e "${GREEN}All tests passed! Ready for deployment. 🚀${NC}"
    exit 0
fi
