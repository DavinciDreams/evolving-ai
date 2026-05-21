# Use Python 3.12 slim image (ai-sdk-python requires >=3.12)
FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    wget \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Runtime storage defaults. These paths are mounted as persistent volumes by
# docker-compose.yaml and should be configured as persistent storage in Coolify
# if deploying this Dockerfile directly.
ENV MEMORY_PERSIST_DIRECTORY=/app/data/memory_db \
    PERSISTENT_DATA_DIR=/app/data/persistent_data \
    KNOWLEDGE_BASE_PATH=/app/data/knowledge_base \
    BACKUP_DIRECTORY=/app/data/backups \
    SCRATCHPAD_DIR=/app/data/scratchpad \
    LOG_FILE=/app/logs/agent.log

# Create necessary directories
RUN mkdir -p \
    /app/data/memory_db \
    /app/data/persistent_data \
    /app/data/knowledge_base \
    /app/data/backups \
    /app/data/scratchpad \
    /app/logs

VOLUME ["/app/data/memory_db", "/app/data/persistent_data", "/app/data/knowledge_base", "/app/data/backups", "/app/data/scratchpad", "/app/logs"]

# Default port (overridable via PORT env var in Coolify/hosting)
ENV PORT=8000
EXPOSE ${PORT}

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:${PORT}/health || exit 1

# Run behind reverse proxies (Traefik/Cloudflare) with forwarded headers enabled
CMD uvicorn evolving_agent.utils.api_server:app --host 0.0.0.0 --port ${PORT} --proxy-headers --forwarded-allow-ips="*"
