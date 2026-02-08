#!/bin/bash
# Network connectivity diagnostic for Coolify/Traefik

echo "=== Evolving AI Network Diagnostic ==="
echo ""

# Find the container
CONTAINER=$(docker ps --filter "name=evolving" --format "{{.Names}}" | head -1)

if [ -z "$CONTAINER" ]; then
    echo "❌ No running container found with 'evolving' in the name"
    exit 1
fi

echo "✅ Found container: $CONTAINER"
CONTAINER_ID=$(docker ps --filter "name=$CONTAINER" --format "{{.ID}}")
echo "   Container ID: $CONTAINER_ID"
echo ""

# Check which networks the container is on
echo "=== Container Networks ==="
docker inspect $CONTAINER | jq -r '.[0].NetworkSettings.Networks | keys[]' 2>/dev/null || docker inspect $CONTAINER --format '{{range $k, $v := .NetworkSettings.Networks}}{{$k}} {{end}}'
echo ""

# Check if container is on coolify network
echo "=== Checking Coolify Network ==="
COOLIFY_NETWORK=$(docker network ls --filter "name=coolify" --format "{{.Name}}" | head -1)
if [ -z "$COOLIFY_NETWORK" ]; then
    echo "⚠️  No 'coolify' network found"
    echo "   Available networks:"
    docker network ls --format "table {{.Name}}\t{{.Driver}}\t{{.Scope}}"
else
    echo "✅ Found network: $COOLIFY_NETWORK"

    # Check if container is connected to coolify network
    IS_CONNECTED=$(docker network inspect $COOLIFY_NETWORK --format '{{range $k, $v := .Containers}}{{$k}} {{end}}' | grep -o $CONTAINER_ID)

    if [ -z "$IS_CONNECTED" ]; then
        echo "❌ Container is NOT connected to $COOLIFY_NETWORK"
        echo ""
        echo "   Containers on $COOLIFY_NETWORK:"
        docker network inspect $COOLIFY_NETWORK --format '{{range $k, $v := .Containers}}{{printf "   - %s (%s)\n" $v.Name $k}}{{end}}'
    else
        echo "✅ Container IS connected to $COOLIFY_NETWORK"

        # Get container IP on coolify network
        CONTAINER_IP=$(docker inspect $CONTAINER --format '{{range $k, $v := .NetworkSettings.Networks}}{{if eq $k "'$COOLIFY_NETWORK'"}}{{$v.IPAddress}}{{end}}{{end}}')
        echo "   Container IP: $CONTAINER_IP"
    fi
fi
echo ""

# Find Traefik container
echo "=== Traefik Proxy ==="
TRAEFIK=$(docker ps --filter "name=traefik" --format "{{.Names}}" | head -1)
if [ -z "$TRAEFIK" ]; then
    echo "⚠️  No Traefik container found"
    echo "   Looking for any proxy:"
    docker ps --filter "name=proxy" --format "{{.Names}}"
else
    echo "✅ Found Traefik: $TRAEFIK"

    # Check if Traefik is on same network
    TRAEFIK_ON_COOLIFY=$(docker network inspect $COOLIFY_NETWORK --format '{{range $k, $v := .Containers}}{{$v.Name}} {{end}}' 2>/dev/null | grep -o "$TRAEFIK")

    if [ -z "$TRAEFIK_ON_COOLIFY" ]; then
        echo "⚠️  Traefik might not be on $COOLIFY_NETWORK"
    else
        echo "✅ Traefik is on $COOLIFY_NETWORK"

        # Test connectivity from Traefik to container
        if [ -n "$CONTAINER_IP" ]; then
            echo ""
            echo "=== Testing Connectivity from Traefik to Container ==="
            echo "Testing: http://$CONTAINER_IP:8000/health"
            docker exec $TRAEFIK wget -qO- --timeout=5 http://$CONTAINER_IP:8000/health 2>/dev/null && echo "✅ Traefik CAN reach container" || echo "❌ Traefik CANNOT reach container"
        fi
    fi
fi
echo ""

# Check Traefik labels on container
echo "=== Traefik Labels on Container ==="
docker inspect $CONTAINER --format '{{range $k, $v := .Config.Labels}}{{if contains $k "traefik"}}{{printf "%s = %s\n" $k $v}}{{end}}{{end}}' | sort
echo ""

# Check container port exposure
echo "=== Container Port Configuration ==="
echo "Exposed ports:"
docker inspect $CONTAINER --format '{{range $port, $conf := .Config.ExposedPorts}}{{$port}} {{end}}'
echo ""
echo "Published ports (should be empty for Traefik routing):"
docker port $CONTAINER 2>/dev/null || echo "None"
echo ""

# Test endpoint from inside container
echo "=== Internal Container Test ==="
docker exec $CONTAINER curl -s -o /dev/null -w "Status: %{http_code}\n" http://localhost:8000/health 2>/dev/null || echo "Failed to test"
echo ""

echo "=== Diagnostic Summary ==="
echo "1. Verify container is on the same network as Traefik (usually 'coolify')"
echo "2. Check Traefik labels are correctly set with port 8000"
echo "3. Ensure no host port mapping (should be empty above)"
echo "4. Confirm Traefik can reach container IP on port 8000"
echo ""
echo "If container is not on coolify network, you may need to:"
echo "- Check Coolify service network settings"
echo "- Ensure service is configured to use the correct network"
echo "- Restart the service after network changes"
