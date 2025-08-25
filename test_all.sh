#!/bin/bash

# Comprehensive testing script for Claude Code
# This script must be run after any code changes

set -e  # Exit on any error

echo "🧪 Running comprehensive test suite..."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

# 1. Run unit tests
echo "1️⃣ Running unit tests..."
if pytest --tb=short -v; then
    print_status "Unit tests passed"
else
    print_error "Unit tests failed"
    exit 1
fi

# 2. Run code quality checks
echo ""
echo "2️⃣ Running code quality checks..."
if black app/ tests/ && isort app/ tests/ && ruff check app/ tests/ && mypy app/; then
    print_status "Code quality checks passed"
else
    print_error "Code quality checks failed"
    exit 1
fi

# 3. Start server and run API smoke tests
echo ""
echo "3️⃣ Starting server for API smoke tests..."

# Create test file
echo "Sample tender document for testing API endpoints" > /tmp/test_api_file.txt

# Start server in background
python run_dev.py &
SERVER_PID=$!

# Wait for server to start
echo "Waiting for server to start..."
sleep 5

# Function to cleanup
cleanup() {
    echo "Cleaning up..."
    kill $SERVER_PID 2>/dev/null || true
    rm -f /tmp/test_api_file.txt
}

# Set trap to cleanup on exit
trap cleanup EXIT

# Test API endpoints
echo ""
echo "4️⃣ Running API smoke tests..."

# Test health endpoint
echo "Testing health endpoint..."
if curl -s -f "http://localhost:8000/health" > /dev/null; then
    print_status "Health endpoint working"
else
    print_error "Health endpoint failed"
    exit 1
fi

# Test batch extraction endpoint
echo "Testing batch extraction endpoint..."
RESPONSE=$(curl -s -X POST "http://localhost:8000/api/v1/extract/batch" \
    -H "Content-Type: multipart/form-data" \
    -F "files=@/tmp/test_api_file.txt" \
    -F "config_name=default")

if echo "$RESPONSE" | grep -q "job_id"; then
    print_status "Batch extraction endpoint working"
    JOB_ID=$(echo "$RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin)['job_id'])")
else
    print_error "Batch extraction endpoint failed"
    echo "Response: $RESPONSE"
    exit 1
fi

# Test job status endpoint
echo "Testing job status endpoint..."
if curl -s -f "http://localhost:8000/api/v1/jobs/$JOB_ID" > /dev/null; then
    print_status "Job status endpoint working"
else
    print_error "Job status endpoint failed"
    exit 1
fi

# Test jobs listing endpoint
echo "Testing jobs listing endpoint..."
if curl -s -f "http://localhost:8000/api/v1/jobs" > /dev/null; then
    print_status "Jobs listing endpoint working"
else
    print_error "Jobs listing endpoint failed"
    exit 1
fi

# Test statistics endpoint
echo "Testing statistics endpoint..."
if curl -s -f "http://localhost:8000/api/v1/statistics" > /dev/null; then
    print_status "Statistics endpoint working"
else
    print_error "Statistics endpoint failed"
    exit 1
fi

# Test that removed single document endpoint returns 404
echo "Testing removed single document endpoint..."
RESPONSE=$(curl -s -w "%{http_code}" "http://localhost:8000/api/v1/extract" -X POST -H "Content-Type: multipart/form-data" -F "file=@/tmp/test_api_file.txt")
if echo "$RESPONSE" | grep -q "404"; then
    print_status "Single document endpoint correctly removed (404)"
else
    print_error "Single document endpoint should return 404"
    exit 1
fi

echo ""
print_status "🎉 All tests passed! API is working correctly."
print_status "📊 Summary:"
print_status "  • Unit tests: PASSED"
print_status "  • Code quality: PASSED"  
print_status "  • API endpoints: PASSED"
print_status "  • Removed endpoints: CORRECTLY 404"

cleanup