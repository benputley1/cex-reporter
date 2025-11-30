# ALKIMI CEX + DEX Reporter & Slack Bot
# Multi-stage build for production deployment on Railway
#
# Supports two deployment modes:
# 1. Bot Service (always-on): python bot_main.py
# 2. Cron Service (hourly): python main.py --mode refresh

FROM python:3.11-slim as builder

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements first for caching
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Production stage
FROM python:3.11-slim

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH

# Copy application code
COPY . .

# Create directories for data and logs
# NOTE: In Railway, /app/data will be mounted as a shared volume
RUN mkdir -p /app/data /app/data/snapshots /app/data/functions /app/logs

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV MOCK_MODE=false

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import sys; sys.exit(0)"

# Default command - overridden by railway.toml
# Bot service: python bot_main.py
# Cron service: python main.py --mode refresh
CMD ["python", "bot_main.py"]
