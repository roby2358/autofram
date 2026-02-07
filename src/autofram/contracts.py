import asyncio
import logging
import re
from pathlib import Path

import claude_code_sdk

log = logging.getLogger(__name__)

MAX_TURNS = 30
ALLOWED_TOOLS = [
    "Read", "Edit", "Write", "Bash", "Glob", "Grep", "WebSearch", "WebFetch"
]
PROMPT_FILES = ["CONTRACTOR.md", "CODING.md"]


def contracts_dir():
    return Path.cwd() / "contracts"


def prompts_dir():
    return Path.cwd() / "static" / "prompts"


def _build_system_prompt():
    parts = [(prompts_dir() / name).read_text().strip() for name in PROMPT_FILES]
    return "\n\n---\n\n".join(parts)


def _parse_title(text):
    match = re.search(r"^# (.+)$", text, re.MULTILINE)
    if match:
        return match.group(1).strip()
    for line in text.splitlines():
        if line.strip():
            return line.strip()
    return "empty"


def _is_pending(text):
    return bool(re.search(r"^pending\s*$", text, re.MULTILINE))


def _find_pending():
    cdir = contracts_dir()
    if not cdir.exists():
        return []
    return [p for p in sorted(cdir.glob("*.md")) if _is_pending(p.read_text())]


async def execute_contract(path):
    path = Path(path)
    text = path.read_text()
    title = _parse_title(text)
    log.info("Executing contract: %s", title)

    prompt = f"Contract file: {path.resolve()}\n\n{text}"

    try:
        messages = []
        async for msg in claude_code_sdk.query(
            prompt=prompt,
            options=claude_code_sdk.ClaudeCodeOptions(
                model="sonnet",
                max_turns=MAX_TURNS,
                permission_mode="bypassPermissions",
                allowed_tools=ALLOWED_TOOLS,
                cwd=str(Path.cwd()),
                system_prompt=_build_system_prompt(),
            ),
        ):
            if hasattr(msg, "content"):
                messages.append(str(msg.content))

        log.info("Contract completed: %s", title)
        return f"completed: {title}"

    except Exception as e:
        log.error("Contract failed: %s — %s", title, e)
        return f"failed: {title} — {e}"


async def execute_contracts():
    pending = _find_pending()
    if not pending:
        return "No pending contracts found."

    results = []
    for path in pending:
        results.append(await execute_contract(path))

    summary = f"Executed {len(results)} contract(s):\n"
    summary += "\n".join(f"- {r}" for r in results)
    return summary
