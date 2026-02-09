import logging
from pathlib import Path

import claude_agent_sdk

from autofram.logger_out import log_to_file, logs_dir, truncate_for_display

log = logging.getLogger(__name__)

MAX_TURNS = 30
ALLOWED_TOOLS = [
    "Read", "Edit", "Write", "Bash", "Glob", "Grep", "WebSearch", "WebFetch"
]
PROMPT_FILES = ["CONTRACTOR.md", "CODING.md"]


class Agent:
    def __init__(self, prompts_dir=None):
        self.prompts_dir = prompts_dir or Path.cwd() / "static" / "prompts"

    def _build_system_prompt(self):
        parts = [(self.prompts_dir / name).read_text().strip() for name in PROMPT_FILES]
        return "\n\n---\n\n".join(parts)

    async def _query(self, title, system_prompt, prompt):
        last_content = "no content"
        async for msg in claude_agent_sdk.query(
            prompt=prompt,
            options=claude_agent_sdk.ClaudeAgentOptions(
                model="sonnet",
                max_turns=MAX_TURNS,
                permission_mode="bypassPermissions",
                allowed_tools=ALLOWED_TOOLS,
                cwd=str(Path.cwd()),
                system_prompt=system_prompt,
            ),
        ):
            if hasattr(msg, "content"):
                last_content = str(msg.content)
                log.info("[%s] %s", title, truncate_for_display(last_content))
                log_to_file(logs_dir() / "contracts.log", f"[{title}] {last_content}")
        return last_content

    async def run(self, title, prompt):
        return await self._query(title, self._build_system_prompt(), prompt)


_default_agent = Agent()


async def run_agent(title, prompt):
    return await _default_agent.run(title, prompt)
