#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
IMAGE_NAME="autofram"
CONTAINER_NAME="autofram-agent"

# Load .env if present
if [ -f "$SCRIPT_DIR/.env" ]; then
    export $(grep -v '^#' "$SCRIPT_DIR/.env" | xargs)
fi

# Check for required environment variable
if [ -z "$OPENROUTER_API_KEY" ]; then
    echo "Error: OPENROUTER_API_KEY is not set"
    echo "Please create a .env file with OPENROUTER_API_KEY=your_key_here"
    exit 1
fi

# Default remote repo location
REMOTE_REPO="${AUTOFRAM_REMOTE:-$HOME/autofram-remote}"

usage() {
    echo "Usage: $0 {build|run|stop|logs|shell}"
    echo ""
    echo "Commands:"
    echo "  build   Build the container image"
    echo "  run     Run the agent container"
    echo "  stop    Stop the running container"
    echo "  logs    Show container logs"
    echo "  shell   Open a shell in the running container"
    echo ""
    echo "Environment variables:"
    echo "  AUTOFRAM_REMOTE   Path to bare git repo (default: ~/autofram-remote)"
}

build() {
    echo "Building $IMAGE_NAME image..."
    podman build -t "$IMAGE_NAME" "$SCRIPT_DIR"
}

run() {
    # Check if remote repo exists
    if [ ! -d "$REMOTE_REPO" ]; then
        echo "Error: Remote repo not found at $REMOTE_REPO"
        echo "Create it with: git init --bare $REMOTE_REPO"
        exit 1
    fi

    echo "Starting $CONTAINER_NAME..."
    podman run -d \
        --name "$CONTAINER_NAME" \
        --cap-drop=ALL \
        --cap-add=NET_ADMIN \
        --security-opt=no-new-privileges \
        -v "$REMOTE_REPO:/mnt/remote:z" \
        -e "OPENROUTER_API_KEY=$OPENROUTER_API_KEY" \
        -e "OPENROUTER_MODEL=${OPENROUTER_MODEL:-anthropic/claude-sonnet-4-5}" \
        -e "GIT_USER_NAME=${GIT_USER_NAME:-autofram}" \
        -e "GIT_USER_EMAIL=${GIT_USER_EMAIL:-autofram@localhost}" \
        "$IMAGE_NAME"

    echo "Container started. View logs with: $0 logs"
}

stop() {
    echo "Stopping $CONTAINER_NAME..."
    podman stop "$CONTAINER_NAME" 2>/dev/null || true
    podman rm "$CONTAINER_NAME" 2>/dev/null || true
    echo "Container stopped."
}

logs() {
    podman logs -f "$CONTAINER_NAME"
}

shell() {
    podman exec -it "$CONTAINER_NAME" /bin/bash
}

case "${1:-}" in
    build)
        build
        ;;
    run)
        run
        ;;
    stop)
        stop
        ;;
    logs)
        logs
        ;;
    shell)
        shell
        ;;
    *)
        usage
        exit 1
        ;;
esac
