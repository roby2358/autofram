#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
IMAGE_NAME="autofram"
CONTAINER_NAME="autofram-agent"

if [ -f "$SCRIPT_DIR/.env" ]; then
    export $(grep -v '^#' "$SCRIPT_DIR/.env" | xargs)
fi

REQUIRED_VARS="OPENROUTER_API_KEY OPENROUTER_MODEL GIT_USER_NAME GIT_USER_EMAIL AUTOFRAM_REMOTE WORK_INTERVAL_MINUTES CLAUDE_CODE_OAUTH_TOKEN"
for var in $REQUIRED_VARS; do
    if [ -z "${!var}" ]; then
        echo "Error: $var is not set. See .env.example."
        exit 1
    fi
done

REMOTE_REPO="${AUTOFRAM_REMOTE/#\~/$HOME}"

run() {
    if [ ! -d "$REMOTE_REPO" ]; then
        echo "Error: Remote repo not found at $REMOTE_REPO"
        echo "Create it with: git init --bare $REMOTE_REPO"
        exit 1
    fi
    echo "Starting $CONTAINER_NAME..."
    podman run -d \
        --name "$CONTAINER_NAME" \
        --cap-drop=ALL \
        --cap-add=NET_ADMIN,SETUID,SETGID \
        --network pasta \
        -v "$REMOTE_REPO:/mnt/remote:z" \
        -p 8080:8080 \
        --env-file "$SCRIPT_DIR/.env" \
        "$IMAGE_NAME"
    echo "Container started. View logs with: $0 logs"
}

stop() {
    echo "Stopping $CONTAINER_NAME..."
    podman stop "$CONTAINER_NAME" 2>/dev/null || true
    podman rm "$CONTAINER_NAME" 2>/dev/null || true
    echo "Container stopped."
}

case "${1:-}" in
    build)    podman build -t "$IMAGE_NAME" "$SCRIPT_DIR" ;;
    run)      run ;;
    stop)     stop ;;
    restart)  podman stop -t 30 "$CONTAINER_NAME" && podman start "$CONTAINER_NAME" ;;
    rebuild)  stop; podman build -t "$IMAGE_NAME" "$SCRIPT_DIR"; run ;;
    logs)     podman logs -f "$CONTAINER_NAME" ;;
    shell)    podman exec -it "$CONTAINER_NAME" /bin/bash ;;
    *)
        echo "Usage: $0 {build|run|stop|restart|rebuild|logs|shell}"
        exit 1
        ;;
esac
