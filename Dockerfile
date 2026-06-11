FROM python:3.11-slim

WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Install dependencies first so they cache independently of source changes
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev

# Copy application code and install the project itself
COPY README.md LICENSE server.py ./
COPY newrelic_mcp/ ./newrelic_mcp/
COPY newrelic-config.json.example .
RUN uv sync --frozen --no-dev

# Create non-root user and setup directories with proper permissions
RUN useradd -r -s /bin/false mcp && \
    mkdir -p /app/config /home/mcp/.cache && \
    chown -R mcp:mcp /app /home/mcp

USER mcp

# Default command - can be overridden with docker run
CMD ["uv", "run", "python", "server.py"]
