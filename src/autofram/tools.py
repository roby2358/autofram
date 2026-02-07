"""MCP tool definitions for the autofram agent."""

import asyncio
import inspect
import os
import subprocess
import sys
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from ddgs import DDGS

from autofram.contracts import execute_contracts as _execute_contracts
from autofram.filesystem import FileSystem
from autofram.git import Git

mcp = FastMCP("autofram")

# Tool execution timeout
BASH_TIMEOUT = 300  # 5 minutes


def touch_bootstrap() -> None:
    """Signal that a bootstrap is in progress.

    Writes a touch file in main's logs directory so the watcher
    knows not to panic during the transition.
    """
    touch_file = Git.get_branch_dir("main") / "logs" / "bootstrapping"
    touch_file.parent.mkdir(exist_ok=True)
    touch_file.touch()


def exec_bootstrap(target_dir: Path) -> None:
    """Replace current process with bootstrap.sh from target directory.

    This runs the target branch's bootstrap.sh which handles:
    - Installing dependencies (may have changed in the new branch)
    - Starting server and watcher
    - Launching the runner

    Args:
        target_dir: Directory containing the bootstrap.sh to exec
    """
    bootstrap_path = target_dir / "bootstrap.sh"
    os.chdir(target_dir)
    os.execv("/bin/bash", ["/bin/bash", str(bootstrap_path)])


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

    Use this to inspect source code, configuration files, COMMS.md, logs, or any
    text file. Always read files before modifying them.

    Args:
        path: Path to the file to read (relative to working directory or absolute)

    Returns:
        The contents of the file as a string

    Raises:
        FileNotFoundError: If the file does not exist
    """
    file_path = FileSystem.resolve_path(path, Path.cwd())

    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    return file_path.read_text()


@mcp.tool()
def write_file(path: str, content: str) -> str:
    """Write content to a file, creating directories if needed.

    Use this to create or overwrite files. Parent directories are created
    automatically. For modifying existing files, read them first to understand
    their current content.

    Args:
        path: Path to the file to write (relative to working directory or absolute)
        content: The complete content to write (overwrites existing content)

    Returns:
        Confirmation message with bytes written
    """
    file_path = FileSystem.resolve_path(path, Path.cwd())
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(content)
    return f"Successfully wrote {len(content)} bytes to {path}"


@mcp.tool()
def bash(command: str) -> str:
    """Execute a shell command and return the output.

    Use this for git operations, running tests, installing dependencies, or any
    shell command. Commands run in the current working directory.

    Common uses:
    - Git: git status, git add, git commit, git push, git pull, git checkout
    - Testing: uv run pytest
    - Directory listing: ls, find
    - Process info: ps, which

    Args:
        command: The bash command to execute

    Returns:
        Combined stdout and stderr output, plus exit code if non-zero

    Note:
        Commands timeout after 5 minutes. Long-running commands should be avoided.
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
    replaced with the runner from the target branch. Use this to switch to
    a different version of your code after making and pushing changes.

    IMPORTANT: Always commit and push your changes before calling bootstrap.
    Uncommitted changes will be lost when the process is replaced.

    Typical workflow:
    1. Create a feature branch
    2. Make and test changes
    3. Commit and push to the branch
    4. Call bootstrap(branch) to switch to the new code
    5. After verifying stability, merge to main
    6. Call bootstrap("main") to return to main

    Args:
        branch: The git branch to bootstrap to (must exist on remote)

    Note:
        This function does not return - it replaces the current process.
    """
    touch_bootstrap()
    target_dir = Git.get_branch_dir(branch)
    clone_or_update_branch(branch, target_dir)
    exec_bootstrap(target_dir)


@mcp.tool()
def rollback() -> None:
    """Bootstrap to main branch to recover from a bad state.

    Use this when the current branch is broken or unstable. This is equivalent
    to calling bootstrap("main") but with clearer intent for error recovery.

    After rollback, you will be running from main and can:
    - Investigate what went wrong on the feature branch
    - Fix issues and push corrections
    - Delete the problematic branch and start fresh

    Note:
        This function does not return - it replaces the current process.
    """
    touch_bootstrap()
    target_dir = Git.get_branch_dir("main")
    clone_or_update_branch("main", target_dir)
    exec_bootstrap(target_dir)


@mcp.tool()
async def execute_contracts() -> str:
    """Execute all pending contracts in the contracts/ directory.

    Scans contracts/ for markdown files with Status: pending, runs each one
    sequentially via the Claude Agent SDK, and returns a summary of outcomes.

    Use this after creating contract files in contracts/. Each contract is
    executed by a separate Claude agent that does the actual work. The agent
    only modifies files — git operations are your responsibility.

    Returns:
        Summary of contract execution results
    """
    return await _execute_contracts()


@mcp.tool()
def web_search(query: str, max_results: int) -> str:
    """Search the web using DuckDuckGo.

    Use this to find documentation, research solutions, look up error messages,
    or gather information about libraries and APIs. Results include titles,
    URLs, and text snippets.

    Args:
        query: The search query (be specific for better results)
        max_results: Maximum number of results to return

    Returns:
        Formatted search results with titles, URLs, and snippets separated by ---

    Example queries:
        "Python subprocess timeout example"
        "FastMCP tool schema format"
        "git rebase vs merge best practices"
    """
    results = DDGS().text(query, max_results=max_results)

    if not results:
        return "No results found."

    formatted = []
    for r in results:
        formatted.append(f"**{r['title']}**\n{r['href']}\n{r['body']}\n")

    return "\n---\n".join(formatted)


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

    if inspect.iscoroutine(result):
        result = asyncio.run(result)

    # bootstrap and rollback don't return (they exec)
    if result is None:
        return "Tool executed successfully"
    return str(result)
