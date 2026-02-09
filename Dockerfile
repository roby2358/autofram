FROM python:3.12-slim

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    less \
    nftables \
    nodejs \
    npm \
    postgresql \
    procps \
    vim \
    && rm -rf /var/lib/apt/lists/* \
    && echo "alias ll='ls -lA'" >> /etc/bash.bashrc

# Install Claude Code CLI
RUN npm install -g @anthropic-ai/claude-code

# Install uv package manager
RUN pip install --no-cache-dir uv

# Create non-root user for Claude Code SDK (which refuses to run as root)
RUN useradd -m -s /bin/bash agent \
    && CLAUDE_REAL=$(which claude) \
    && mv "$CLAUDE_REAL" "${CLAUDE_REAL}.real" \
    && printf '#!/bin/bash\nexec runuser -u agent -- "${0}.real" "$@"\n' > "$CLAUDE_REAL" \
    && chmod +x "$CLAUDE_REAL"

# Create agent directory structure (owned by agent so Claude Code can write)
RUN mkdir -p /agent/main && chown -R agent:agent /agent

# Copy minimal bootloader entrypoint only
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Expose status server port
EXPOSE 8080

# Set entrypoint
CMD ["/entrypoint.sh"]
