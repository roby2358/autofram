"""MCP tool definitions for the autofram agent."""

import os
import subprocess
import sys
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from autofram.filesystem import FileSystem
from autofram.git import Git

mcp = FastMCP("autofram")

# Tool execution timeout
BASH_TIMEOUT = 300  # 5 minutes


def exec_runner(target_dir: Path) -> None:
    """Replace current process with runner from target directory.

    Args:
        target_dir: Directory containing the runner to exec
    """
    runner_path = target_dir / "src" / "autofram" / "runner.py"
    os.chdir(target_dir)
    os.execv(sys.executable, [sys.executable, str(runner_path)])


def clone_or_update_branch(branch: str, target_dir: Path) -> None:
    """Clone a branch or update an existing clone.

    Args:
        branch: Git branch name
        target_dir: Target directory for the clone
    """
    if target_dir.exists():
        Git.run(["fetch", "origin"], cwd=target_dir)
        Git.run(["checkout", branch], cwd=target_dir)
        Git.run(["reset", "--hard", f"origin/{branch}"], cwd=target_dir)
    else:
        target_dir.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            ["git", "clone", "-b", branch, str(Git.REMOTE_REPO), str(target_dir)],
            check=True,
        )


def format_bash_output(result: subprocess.CompletedProcess) -> str:
    """Format bash command output for return.

    Args:
        result: Completed process from subprocess.run

    Returns:
        Formatted output string
    """
    parts = []
    if result.stdout:
        parts.append(result.stdout)
    if result.stderr:
        parts.append(result.stderr)
    if result.returncode != 0:
        parts.append(f"[Exit code: {result.returncode}]")

    output = "\n".join(parts) if parts else "[No output]"
    return output


@mcp.tool()
def read_file(path: str) -> str:
    """Read the contents of a file.

    Args:
        path: Path to the file to read (relative to working directory or absolute)

    Returns:
        The contents of the file as a string
    """
    file_path = FileSystem.resolve_path(path)

    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    return file_path.read_text()


@mcp.tool()
def write_file(path: str, content: str) -> str:
    """Write content to a file, creating directories if needed.

    Args:
        path: Path to the file to write (relative to working directory or absolute)
        content: The content to write to the file

    Returns:
        Confirmation message
    """
    file_path = FileSystem.resolve_path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(content)
    return f"Successfully wrote {len(content)} bytes to {path}"


@mcp.tool()
def bash(command: str) -> str:
    """Execute a shell command and return the output.

    Args:
        command: The bash command to execute

    Returns:
        Combined stdout and stderr output from the command
    """
    result = subprocess.run(
        command,
        shell=True,
        capture_output=True,
        text=True,
        timeout=BASH_TIMEOUT,
    )
    return format_bash_output(result)


@mcp.tool()
def bootstrap(branch: str) -> None:
    """Clone/update target branch and exec its runner, replacing this process.

    This implements the hop-scotch upgrade pattern. The current process is
    replaced with the runner from the target branch.

    Args:
        branch: The git branch to bootstrap to
    """
    target_dir = Git.get_branch_dir(branch)
    clone_or_update_branch(branch, target_dir)
    (target_dir / "logs").mkdir(exist_ok=True)
    exec_runner(target_dir)


@mcp.tool()
def rollback() -> None:
    """Bootstrap to main branch to recover from a bad state.

    Use this when the current branch is broken. The runner on main can then
    investigate the feature branch, fix issues, or delete it and start over.
    """
    target_dir = Git.get_branch_dir("main")
    clone_or_update_branch("main", target_dir)
    (target_dir / "logs").mkdir(exist_ok=True)
    exec_runner(target_dir)


def get_tools_for_openai() -> list[dict]:
    """Get tool schemas from FastMCP in OpenAI function calling format.

    Returns:
        List of tool definitions in OpenAI format
    """
    tools = []
    for tool in mcp._tool_manager._tools.values():
        schema = {
            "name": tool.name,
            "description": tool.description or "",
            "parameters": tool.parameters,
        }
        tools.append({"type": "function", "function": schema})
    return tools


def execute_tool(name: str, arguments: dict) -> str:
    """Execute a tool by name with given arguments.

    Args:
        name: The name of the tool to execute
        arguments: Dictionary of arguments to pass to the tool

    Returns:
        The result of the tool execution as a string
    """
    tool = mcp._tool_manager._tools.get(name)
    if tool is None:
        raise ValueError(f"Unknown tool: {name}")

    result = tool.fn(**arguments)

    # bootstrap and rollback don't return (they exec)
    if result is None:
        return "Tool executed successfully"
    return str(result)
