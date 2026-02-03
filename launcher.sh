#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
IMAGE_NAME="autofram"
CONTAINER_NAME="autofram-agent"

# Load .env if present
if [ -f "$SCRIPT_DIR/.env" ]; then
    export $(grep -v '^#' "$SCRIPT_DIR/.env" | xargs)
fi

# Check for required environment variables
REQUIRED_VARS="OPENROUTER_API_KEY OPENROUTER_MODEL GIT_USER_NAME GIT_USER_EMAIL AUTOFRAM_REMOTE"
for var in $REQUIRED_VARS; do
    if [ -z "${!var}" ]; then
        echo "Error: $var is not set"
        echo "Please set all required variables in .env (see .env.example)"
        exit 1
    fi
done

# Expand tilde in path (~ doesn't expand when loaded from .env)
REMOTE_REPO="${AUTOFRAM_REMOTE/#\~/$HOME}"

usage() {
    echo "Usage: $0 {build|run|stop|rebuild|logs|shell}"
    echo ""
    echo "Commands:"
    echo "  build     Build the container image"
    echo "  run       Run the agent container"
    echo "  stop      Stop the running container"
    echo "  rebuild   Stop, build, and run"
    echo "  logs      Show container logs"
    echo "  shell     Open a shell in the running container"
    echo ""
    echo "All variables in .env are required. See .env.example."
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
        -p 8080:8080 \
        -e "OPENROUTER_API_KEY=$OPENROUTER_API_KEY" \
        -e "OPENROUTER_MODEL=$OPENROUTER_MODEL" \
        -e "GIT_USER_NAME=$GIT_USER_NAME" \
        -e "GIT_USER_EMAIL=$GIT_USER_EMAIL" \
        "$IMAGE_NAME"

    echo "Container started. View logs with: $0 logs"
}

stop() {
    echo "Stopping $CONTAINER_NAME..."
    podman stop "$CONTAINER_NAME" 2>/dev/null || true
    podman rm "$CONTAINER_NAME" 2>/dev/null || true
    echo "Container stopped."
}

rebuild() {
    stop
    build
    run
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
    rebuild)
        rebuild
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
