#!/usr/bin/env python3
"""Main LLM loop for the autofram agent."""

import json
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

from autofram.filesystem import FileSystem
from autofram.git import Git
from autofram.tools import execute_tool, get_tools_for_openai

# Load environment variables
load_dotenv()


class Runner:
    """Main LLM interaction loop for the autofram agent."""

    # Configuration
    OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
    WORK_INTERVAL_MINUTES = 10
    RETRY_DELAY_SECONDS = 60
    DISPLAY_TRUNCATE_LENGTH = 200

    def __init__(self, working_dir: Path | None = None):
        """Initialize the runner.

        Args:
            working_dir: Working directory (defaults to cwd)
        """
        self.working_dir = working_dir or Path.cwd()
        self.system_md = self.working_dir / "static" / "prompts" / "SYSTEM.md"
        self.comms_md = self.working_dir / "COMMS.md"
        self.logs_dir = self.working_dir / "logs"
        self.bootstrap_log = self.logs_dir / "bootstrap.log"
        self.errors_log = self.logs_dir / "errors.log"

        self.api_key = os.environ.get("OPENROUTER_API_KEY")
        self.model = os.environ.get("OPENROUTER_MODEL")

        self.client: OpenAI | None = None
        self.tools: list[dict] | None = None

    def log_bootstrap(self, status: str) -> None:
        """Log a bootstrap event to bootstrap.log."""
        self.logs_dir.mkdir(exist_ok=True)
        timestamp = FileSystem.format_timestamp()
        branch = Git.get_current_branch(self.working_dir)
        with open(self.bootstrap_log, "a") as f:
            f.write(f"{status} {timestamp} {branch}\n")

    def setup_error_logging(self) -> None:
        """Redirect stderr to errors.log, truncating on startup."""
        self.logs_dir.mkdir(exist_ok=True)
        self.errors_log.write_text("")
        sys.stderr = open(self.errors_log, "a")

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
        system_content += "\n\n---\n\n# COMMS.md\n\n"
        system_content += self.load_file_content(self.comms_md, "No COMMS.md found.\n")
        return system_content

    def calculate_sleep_seconds(self) -> float:
        """Calculate seconds until next aligned interval.

        Returns:
            Seconds to sleep (0 if already past target)
        """
        now = datetime.now()
        minutes_to_next = self.WORK_INTERVAL_MINUTES - (now.minute % self.WORK_INTERVAL_MINUTES)
        if minutes_to_next == 0:
            minutes_to_next = self.WORK_INTERVAL_MINUTES
        next_time = now.replace(second=0, microsecond=0) + timedelta(minutes=minutes_to_next)
        return max(0, (next_time - datetime.now()).total_seconds())

    def sleep_until_next_interval(self) -> None:
        """Sleep until the next 10-minute aligned interval."""
        sleep_seconds = self.calculate_sleep_seconds()
        if sleep_seconds > 0:
            next_time = datetime.now() + timedelta(seconds=sleep_seconds)
            print(f"Sleeping until {next_time.strftime('%H:%M')} ({sleep_seconds:.0f}s)")
            time.sleep(sleep_seconds)

    def truncate_for_display(self, text: str) -> str:
        """Truncate text for display with ellipsis."""
        if len(text) > self.DISPLAY_TRUNCATE_LENGTH:
            return f"{text[:self.DISPLAY_TRUNCATE_LENGTH]}..."
        return text

    def execute_tool_call(self, tool_call) -> dict:
        """Execute a single tool call and return the result message.

        Args:
            tool_call: OpenAI tool call object

        Returns:
            Tool result message dict for the conversation
        """
        tool_name = tool_call.function.name
        tool_args = json.loads(tool_call.function.arguments)

        print(f"  Tool: {tool_name}({tool_args})")

        try:
            result = execute_tool(tool_name, tool_args)
            print(f"  Result: {self.truncate_for_display(result)}")
            return {
                "tool_call_id": tool_call.id,
                "role": "tool",
                "content": result,
            }
        except Exception as e:
            error_msg = f"Error: {type(e).__name__}: {e}"
            print(f"  {error_msg}", file=sys.stderr)
            return {
                "tool_call_id": tool_call.id,
                "role": "tool",
                "content": error_msg,
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
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=self.tools,
                tool_choice="auto",
            )
            follow_up = response.choices[0].message

            if not follow_up.tool_calls:
                if follow_up.content:
                    print(f"  Response: {follow_up.content}")
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
            print("ERROR: OPENROUTER_API_KEY not set", file=sys.stderr)
            sys.exit(1)

        return OpenAI(
            api_key=self.api_key,
            base_url=self.OPENROUTER_BASE_URL,
        )

    def run_single_iteration(self) -> None:
        """Run a single iteration of the LLM loop."""
        system_prompt = self.load_system_prompt()
        messages = self.build_messages(system_prompt)

        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Calling LLM...")
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            tools=self.tools,
            tool_choice="auto",
        )

        message = response.choices[0].message

        if message.tool_calls:
            self.process_tool_calls(message, messages)
        elif message.content:
            print(f"  Response: {message.content}")

    def run(self) -> None:
        """Main LLM interaction loop."""
        self.client = self.create_client()
        self.tools = get_tools_for_openai()

        while True:
            try:
                self.run_single_iteration()
                self.sleep_until_next_interval()

            except KeyboardInterrupt:
                print("\nShutdown requested.")
                break
            except Exception as e:
                print(f"ERROR in LLM loop: {type(e).__name__}: {e}", file=sys.stderr)
                time.sleep(self.RETRY_DELAY_SECONDS)

    def start(self) -> None:
        """Main entry point."""
        print(f"Autofram Runner starting in {self.working_dir}")
        print(f"Branch: {Git.get_current_branch(self.working_dir)}")
        print(f"Model: {self.model}")

        self.log_bootstrap("BOOTSTRAPPING")
        self.setup_error_logging()
        self.log_bootstrap("SUCCESS")

        print("Bootstrap successful, entering main loop...")
        self.run()


def main() -> None:
    """Main entry point."""
    runner = Runner()
    runner.start()


if __name__ == "__main__":
    main()
