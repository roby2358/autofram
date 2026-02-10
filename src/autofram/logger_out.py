import json
import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from autofram.filesystem import UTC_FORMAT, FileSystem
from autofram.git import Git


class LogFile:
    def __init__(self, logfile_path):
        self.path = Path(logfile_path)

    def _write(self, level, msg):
        LoggerOut.write_log(self.path, f"{level}: {msg}")

    def info(self, msg):
        self._write("INFO", msg)

    def error(self, msg):
        self._write("ERROR", msg)

    def warning(self, msg):
        self._write("WARNING", msg)

    def debug(self, msg):
        self._write("DEBUG", msg)


class LoggerOut:
    MAX_DISPLAY_LENGTH = 80
    LOG_MAX_BYTES = 5 * 1024 * 1024
    LOG_BACKUP_COUNT = 3

    def __init__(self):
        self.logs_dir = Path.cwd() / "logs"
        self.stdlog = logging.getLogger("autofram.runner")

    @staticmethod
    def truncate_for_display(text):
        max_len = LoggerOut.MAX_DISPLAY_LENGTH
        head = text[:max_len + 1]
        endline = head.find("\n")
        if endline != -1:
            return f"{text[:endline]}..."
        if len(head) > max_len:
            return f"{text[:max_len]}..."
        return text

    @staticmethod
    def write_log(logfile, msg):
        logfile = Path(logfile)
        logfile.parent.mkdir(exist_ok=True)
        timestamp = FileSystem.format_timestamp(UTC_FORMAT)
        with open(logfile, "a") as f:
            f.write(f"[{timestamp}] {msg}\n")

    def setup(self):
        self.logs_dir.mkdir(exist_ok=True)
        self.stdlog.setLevel(logging.INFO)
        self.stdlog.propagate = False

        console = logging.StreamHandler(sys.__stdout__)
        console.setFormatter(logging.Formatter("%(message)s"))
        self.stdlog.addHandler(console)

        file_handler = RotatingFileHandler(
            self.logs_dir / "runner.log",
            maxBytes=self.LOG_MAX_BYTES,
            backupCount=self.LOG_BACKUP_COUNT,
            )
        file_handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s %(message)s")
        )
        self.stdlog.addHandler(file_handler)

    def bootstrap(self, working_dir, status):
        branch = Git.get_current_branch(working_dir)
        self.write_log(self.logs_dir / "bootstrap.log", f"{status} {branch}")

    def model(self, direction, data):
        entry = {
            "timestamp": FileSystem.format_timestamp(UTC_FORMAT),
            "direction": direction,
            "data": data,
        }
        logfile = self.logs_dir / "model.log"
        with open(logfile, "a") as f:
            f.write(json.dumps(entry) + "\n")

    def redirect_stderr(self):
        errors_log = self.logs_dir / "errors.log"
        errors_log.write_text("")
        sys.stderr = open(errors_log, "a")

    def __getattr__(self, name):
        if name.startswith("_"):
            raise AttributeError(f"'{type(self).__name__}' object has no attribute '{name}'")
        return LogFile(self.logs_dir / f"{name}.log")


_default_instance = None


def _get_default():
    global _default_instance
    if _default_instance is None:
        _default_instance = LoggerOut()
    return _default_instance


def logs_dir():
    return Path.cwd() / "logs"


def truncate_for_display(text):
    return LoggerOut.truncate_for_display(text)


def log_to_file(logfile, msg):
    LoggerOut.write_log(logfile, msg)


def log_error(errors_log, error_msg):
    LoggerOut.write_log(errors_log, error_msg)


logger = logging.getLogger("autofram.runner")
