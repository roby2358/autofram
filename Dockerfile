FROM python:3.12-slim

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    nftables \
    procps \
    && rm -rf /var/lib/apt/lists/*

# Install uv package manager
RUN pip install --no-cache-dir uv

# Create agent directory structure
RUN mkdir -p /agent/main

# Copy project files
WORKDIR /app
COPY pyproject.toml .
COPY src/ ./src/
COPY entrypoint.sh .

# Install Python dependencies
RUN uv pip install --system -e .

# Make entrypoint executable
RUN chmod +x entrypoint.sh

# Expose status server port
EXPOSE 8080

# Set entrypoint
CMD ["/app/entrypoint.sh"]
