FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl git less nftables nodejs npm postgresql procps vim \
    && rm -rf /var/lib/apt/lists/* \
    && echo "alias ll='ls -lA'" >> /etc/bash.bashrc

RUN npm install -g @anthropic-ai/claude-code \
    && pip install --no-cache-dir uv

# Non-root user for Claude Code SDK (refuses to run as root)
RUN useradd -m -s /bin/bash agent \
    && CLAUDE=$(which claude) \
    && mv "$CLAUDE" "$CLAUDE.real" \
    && printf '#!/bin/bash\nexec runuser -u agent -- "${0}.real" "$@"\n' > "$CLAUDE" \
    && chmod +x "$CLAUDE"

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 8080
CMD ["/entrypoint.sh"]
