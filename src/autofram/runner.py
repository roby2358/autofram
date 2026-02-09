#!/usr/bin/env python3
"""Main LLM loop for the autofram agent."""

import hashlib
import json
import logging
import os
import subprocess
import sys
import time
from datetime import datetime, timedelta
from logging.handlers import RotatingFileHandler
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

from autofram.filesystem import UTC_FORMAT, FileSystem
from autofram.git import Git
from autofram.logger_out import truncate_for_display
from autofram.tools import execute_tool, get_tools_for_openai

# Load environment variables
load_dotenv()


logger = logging.getLogger("autofram.runner")


class Runner:
    """Main LLM interaction loop for the autofram agent."""

    OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
    RETRY_DELAY_SECONDS = 60
    LOG_MAX_BYTES = 5 * 1024 * 1024  # 5 MB
    LOG_BACKUP_COUNT = 3

    def __init__(self, working_dir: Path | None = None):
        """Initialize the runner.

        Args:
            working_dir: Working directory (defaults to cwd)
        """
        self.working_dir = working_dir or Path.cwd()
        self.work_interval_minutes = int(os.environ["WORK_INTERVAL_MINUTES"])
        self.system_md = self.working_dir / "static" / "prompts" / "SYSTEM.md"
        self.comms_md = self.working_dir / "COMMS.md"
        self.logs_dir = self.working_dir / "logs"
        self.bootstrap_log = self.logs_dir / "bootstrap.log"
        self.errors_log = self.logs_dir / "errors.log"
        self.model_log = self.logs_dir / "model.log"

        self.api_key = os.environ.get("OPENROUTER_API_KEY")
        self.model = os.environ.get("OPENROUTER_MODEL")

        self.client: OpenAI | None = None
        self.tools: list[dict] | None = None
        self._last_comms_hash: str | None = None

    def log_bootstrap(self, status: str) -> None:
        """Log a bootstrap event to bootstrap.log."""
        self.logs_dir.mkdir(exist_ok=True)
        timestamp = FileSystem.format_timestamp(UTC_FORMAT)
        branch = Git.get_current_branch(self.working_dir)
        with open(self.bootstrap_log, "a") as f:
            f.write(f"{status} {timestamp} {branch}\n")

    def setup_error_logging(self) -> None:
        """Redirect stderr to errors.log, truncating on startup."""
        self.logs_dir.mkdir(exist_ok=True)
        self.errors_log.write_text("")
        sys.stderr = open(self.errors_log, "a")

    def setup_logging(self) -> None:
        """Configure runner logger with console and rotating file handlers."""
        self.logs_dir.mkdir(exist_ok=True)

        logger.setLevel(logging.INFO)
        logger.propagate = False

        console = logging.StreamHandler(sys.__stdout__)
        console.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(console)

        file_handler = RotatingFileHandler(
            self.logs_dir / "runner.log",
            maxBytes=self.LOG_MAX_BYTES,
            backupCount=self.LOG_BACKUP_COUNT,
        )
        file_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        logger.addHandler(file_handler)

    def log_model(self, direction: str, data: dict) -> None:
        """Log a model API request or response to model.log.

        Args:
            direction: Either "request", "response", or "tool_result"
            data: The request, response, or tool result data to log
        """
        self.logs_dir.mkdir(exist_ok=True)
        entry = {
            "timestamp": FileSystem.format_timestamp(UTC_FORMAT),
            "direction": direction,
            "data": data,
        }
        with open(self.model_log, "a") as f:
            f.write(json.dumps(entry) + "\n")

    def log_error(self, error_msg: str) -> None:
        """Log an error message to errors.log.

        Args:
            error_msg: The error message to log
        """
        self.logs_dir.mkdir(exist_ok=True)
        timestamp = FileSystem.format_timestamp(UTC_FORMAT)
        with open(self.errors_log, "a") as f:
            f.write(f"[{timestamp}] {error_msg}\n")

    def hash_comms(self) -> str | None:
        """Hash the contents of COMMS.md, or None if missing."""
        if not self.comms_md.exists():
            return None
        return hashlib.sha256(self.comms_md.read_bytes()).hexdigest()

    def pull_latest(self) -> None:
        """Pull latest changes from remote."""
        Git.run(["pull", "--ff-only"], cwd=self.working_dir, check=False)

    def load_file_content(self, path: Path, default: str) -> str:
        """Load file content or return default if not found."""
        if path.exists():
            return path.read_text()
        return default

    def load_system_prompt(self) -> str:
        """Load SYSTEM.md and COMMS.md as the system prompt."""
        system_content = self.load_file_content(
            self.system_md, "# Autofram Agent\n\nNo SYSTEM.md found.\n"
        )

        # Add environment context
        context_commands = [
            "pwd",
            "git branch --show-current",
            "find . -type f",
        ]
        system_content += "\n\n---\n\n# Environment\n\n```\n"
        for cmd in context_commands:
            try:
                result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
                system_content += f"$ {cmd}\n{result.stdout.strip()}\n\n"
            except Exception:
                pass
        system_content += "```\n"

        system_content += "\n\n---\n\ncat COMMS.md\n\n"
        system_content += self.load_file_content(self.comms_md, "No COMMS.md found.\n")
        return system_content

    def calculate_sleep_seconds(self) -> float:
        """Calculate seconds until next aligned interval.

        Returns:
            Seconds to sleep (0 if already past target)
        """
        now = datetime.now()
        minutes_to_next = self.work_interval_minutes - (now.minute % self.work_interval_minutes)
        if minutes_to_next == 0:
            minutes_to_next = self.work_interval_minutes
        next_time = now.replace(second=0, microsecond=0) + timedelta(minutes=minutes_to_next)
        return max(0, (next_time - datetime.now()).total_seconds())

    def sleep_until_next_interval(self) -> None:
        """Sleep until the next aligned interval (per WORK_INTERVAL_MINUTES)."""
        sleep_seconds = self.calculate_sleep_seconds()
        if sleep_seconds > 0:
            next_time = datetime.now() + timedelta(seconds=sleep_seconds)
            logger.info("Sleeping until %s (%ds)", next_time.strftime("%H:%M"), sleep_seconds)
            time.sleep(sleep_seconds)

    def execute_tool_call(self, tool_call) -> dict:
        """Execute a single tool call and return the result message.

        Args:
            tool_call: OpenAI tool call object

        Returns:
            Tool result message dict for the conversation
        """
        tool_name = tool_call.function.name
        raw_args = tool_call.function.arguments or "{}"
        tool_args = json.loads(raw_args)
        logger.info("Tool: %s(%s)", tool_name, truncate_for_display(str(tool_args)))

        try:
            content = execute_tool(tool_name, tool_args)
            logger.info("Result: %s", truncate_for_display(content))
        except IsADirectoryError:
            path = tool_args.get('path', '')
            content = f"Error: '{path}' is a directory, not a file. Use bash('ls {path}') to list its contents."
            logger.info("Result: %s", truncate_for_display(content))
        except Exception as e:
            content = f"Error: {type(e).__name__}: {e}"
            args_short = truncate_for_display(str(tool_args))
            logger.error("Tool error in %s(%s): %s", tool_name, args_short, content)
            self.log_error(f"Tool error in {tool_name}({args_short}): {content}")

        self.log_model("tool_result", {
            "tool_name": tool_name,
            "tool_args": tool_args,
            "tool_call_id": tool_call.id,
            "content": content,
        })

        return {
            "tool_call_id": tool_call.id,
            "role": "tool",
            "content": content,
        }

    def process_tool_calls(self, message, messages: list) -> None:
        """Process tool calls from an LLM message, handling nested calls.

        Args:
            message: LLM response message with tool_calls
            messages: Conversation messages list (modified in place)
        """
        # Execute initial tool calls
        tool_results = [self.execute_tool_call(tc) for tc in message.tool_calls]

        messages.append(message.model_dump())
        messages.extend(tool_results)

        # Handle nested tool calls
        while True:
            self.log_model("request", {"messages": messages, "tools": self.tools})

            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=self.tools,
                tool_choice="auto",
            )
            follow_up = response.choices[0].message
            self.log_model("response", follow_up.model_dump())
            logger.info("Response: %s", truncate_for_display(str(follow_up.content)))

            if not follow_up.tool_calls:
                break

            nested_results = [self.execute_tool_call(tc) for tc in follow_up.tool_calls]
            messages.append(follow_up.model_dump())
            messages.extend(nested_results)

    def build_messages(self, system_prompt: str) -> list[dict]:
        """Build the initial messages list for an LLM call."""
        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": "Continue."},
        ]

    def create_client(self) -> OpenAI:
        """Create and return the OpenAI client configured for OpenRouter."""
        if not self.api_key:
            logger.error("OPENROUTER_API_KEY not set")
            sys.exit(1)

        return OpenAI(
            api_key=self.api_key,
            base_url=self.OPENROUTER_BASE_URL,
        )

    def run_single_iteration(self) -> None:
        """Run a single iteration of the LLM loop."""
        self.pull_latest()

        comms_hash = self.hash_comms()
        if comms_hash == self._last_comms_hash:
            logger.info("COMMS.md unchanged, skipping cycle")
            return

        system_prompt = self.load_system_prompt()
        messages = self.build_messages(system_prompt)

        last_msg = messages[-1]
        logger.info("Calling LLM: [%s]: %s", last_msg.get("role", "?"),
                     truncate_for_display(str(last_msg.get("content", ""))))
        self.log_model("request", {"messages": messages, "tools": self.tools})

        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            tools=self.tools,
            tool_choice="auto",
        )

        message = response.choices[0].message
        self.log_model("response", message.model_dump())
        logger.info("Response: %s", truncate_for_display(str(message.content)))

        if message.tool_calls:
            self.process_tool_calls(message, messages)

        self._last_comms_hash = self.hash_comms()

    def run(self) -> None:
        """Main LLM interaction loop."""
        self.client = self.create_client()
        self.tools = get_tools_for_openai()

        while True:
            try:
                self.run_single_iteration()
                self.sleep_until_next_interval()

            except KeyboardInterrupt:
                logger.info("Shutdown requested.")
                break
            except Exception as e:
                logger.error("LLM loop error: %s: %s", type(e).__name__, e)
                time.sleep(self.RETRY_DELAY_SECONDS)

    def start(self) -> None:
        """Main entry point."""
        self.log_bootstrap("BOOTSTRAPPING")
        self.setup_error_logging()
        self.setup_logging()
        self.log_bootstrap("SUCCESS")

        logger.info("Autofram Runner starting in %s", self.working_dir)
        logger.info("Branch: %s", Git.get_current_branch(self.working_dir))
        logger.info("Model: %s", self.model)
        logger.info("Bootstrap successful, entering main loop...")
        self.run()


def main() -> None:
    """Main entry point."""
    runner = Runner()
    runner.start()


if __name__ == "__main__":
    main()
