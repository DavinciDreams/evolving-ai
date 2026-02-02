#!/bin/bash
# Container debugging script for Coolify deployment

echo "=== Evolving AI Container Debug ==="
echo ""

# Find the container
CONTAINER=$(docker ps --filter "name=evolving" --format "{{.Names}}" | head -1)

if [ -z "$CONTAINER" ]; then
    echo "❌ No running container found with 'evolving' in the name"
    echo ""
    echo "Available containers:"
    docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
    exit 1
fi

echo "✅ Found container: $CONTAINER"
echo ""

# Check container status
echo "=== Container Status ==="
docker ps --filter "name=$CONTAINER" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
echo ""

# Check health
echo "=== Health Status ==="
HEALTH=$(docker inspect --format='{{.State.Health.Status}}' $CONTAINER 2>/dev/null || echo "no healthcheck")
echo "Health: $HEALTH"
echo ""

# Test endpoints from inside container
echo "=== Testing Endpoints (from inside container) ==="
echo "Testing /health:"
docker exec $CONTAINER curl -s -o /dev/null -w "Status: %{http_code}\n" http://localhost:8000/health || echo "Failed to reach /health"

echo "Testing / (root):"
docker exec $CONTAINER curl -s http://localhost:8000/ || echo "Failed to reach /"
echo ""

# Test from host
echo "=== Testing Endpoints (from host) ==="
PORT=$(docker port $CONTAINER 8000 2>/dev/null | cut -d: -f2)
if [ -n "$PORT" ]; then
    echo "Container port 8000 mapped to host port: $PORT"
    echo "Testing http://localhost:$PORT/health:"
    curl -s http://localhost:$PORT/health || echo "Failed"
    echo ""
else
    echo "Port 8000 not exposed to host"
fi

# Check logs
echo "=== Recent Logs (last 30 lines) ==="
docker logs $CONTAINER --tail 30
echo ""

# Check environment
echo "=== Key Environment Variables ==="
docker exec $CONTAINER env | grep -E "DEFAULT_LLM_PROVIDER|DEFAULT_MODEL|ZAI_API_KEY" | sed 's/\(.*KEY=\).*/\1***REDACTED***/'
echo ""

echo "=== Debug Complete ==="
echo ""
echo "Next steps:"
echo "1. Check if the app is responding inside the container"
echo "2. Verify port mapping is correct"
echo "3. Check logs for startup errors"
echo "4. Ensure environment variables are set"
