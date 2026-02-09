import json
import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from autofram.filesystem import UTC_FORMAT, FileSystem
from autofram.git import Git


MAX_DISPLAY_LENGTH = 80


def logs_dir():
    return Path.cwd() / "logs"

logger = logging.getLogger("autofram.runner")

LOG_MAX_BYTES = 5 * 1024 * 1024  # 5 MB
LOG_BACKUP_COUNT = 3


def truncate_for_display(text):
    head = text[:MAX_DISPLAY_LENGTH + 1]
    endline = head.find("\n")
    if endline != -1:
        return f"{text[:endline]}..."
    if len(head) > MAX_DISPLAY_LENGTH:
        return f"{text[:MAX_DISPLAY_LENGTH]}..."
    return text


def log_bootstrap(logs_dir, bootstrap_log, working_dir, status):
    logs_dir.mkdir(exist_ok=True)
    timestamp = FileSystem.format_timestamp(UTC_FORMAT)
    branch = Git.get_current_branch(working_dir)
    with open(bootstrap_log, "a") as f:
        f.write(f"{status} {timestamp} {branch}\n")


def setup_error_logging(logs_dir, errors_log):
    logs_dir.mkdir(exist_ok=True)
    errors_log.write_text("")
    sys.stderr = open(errors_log, "a")


def setup_logging(logs_dir):
    logs_dir.mkdir(exist_ok=True)

    logger.setLevel(logging.INFO)
    logger.propagate = False

    console = logging.StreamHandler(sys.__stdout__)
    console.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(console)

    file_handler = RotatingFileHandler(
        logs_dir / "runner.log",
        maxBytes=LOG_MAX_BYTES,
        backupCount=LOG_BACKUP_COUNT,
    )
    file_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(file_handler)


def log_model(logs_dir, model_log, direction, data):
    logs_dir.mkdir(exist_ok=True)
    entry = {
        "timestamp": FileSystem.format_timestamp(UTC_FORMAT),
        "direction": direction,
        "data": data,
    }
    with open(model_log, "a") as f:
        f.write(json.dumps(entry) + "\n")


def log_to_file(logfile, msg):
    logfile.parent.mkdir(exist_ok=True)
    timestamp = FileSystem.format_timestamp(UTC_FORMAT)
    with open(logfile, "a") as f:
        f.write(f"[{timestamp}] {msg}\n")


def log_error(errors_log, error_msg):
    log_to_file(errors_log, error_msg)
