#!/bin/bash
# Quick test script for web search functionality

echo "Testing Web Search Integration"
echo "================================"
echo ""

# Wait for server to be ready
sleep 2

# Test 1: Check web search status
echo "1. Checking web search status..."
curl -s http://localhost:8000/web-search/status | python3 -m json.tool
echo ""
echo ""

# Test 2: Search for AI developments
echo "2. Searching for 'Latest AI developments 2025'..."
curl -s -X POST "http://localhost:8000/web-search" \
  -H "Content-Type: application/json" \
  -d '{"query": "Latest AI developments 2025", "max_results": 3}' | python3 -m json.tool
echo ""
echo ""

# Test 3: Search for Python best practices
echo "3. Searching for 'Python best practices'..."
curl -s -X POST "http://localhost:8000/web-search" \
  -H "Content-Type: application/json" \
  -d '{"query": "Python best practices", "max_results": 3}' | python3 -m json.tool
echo ""

echo "================================"
echo "Web search tests completed!"
