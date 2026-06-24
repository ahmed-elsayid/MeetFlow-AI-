FROM python:3.11-slim

# Prevent apt-get from prompting for timezone or other configurations
ENV DEBIAN_FRONTEND=noninteractive

# Install system dependencies (no audio libs needed — captions are text)
RUN apt-get update && apt-get install -y --no-install-recommends \
    xvfb \
    wget \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv
RUN pip install uv

# Set working directory
WORKDIR /app

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Install dependencies using uv
RUN uv sync --frozen --no-cache

# Install playwright browsers
RUN uv run playwright install chromium
RUN uv run playwright install-deps

# Copy application code
COPY . .

# Copy entrypoint script
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Environment variables for Xvfb
ENV DISPLAY=:99

# Create non-root user
RUN useradd -m -G video botuser && \
    chown -R botuser:botuser /app && \
    chown botuser:botuser /entrypoint.sh

USER botuser

ENTRYPOINT ["/entrypoint.sh"]
