import logging
import re
from pathlib import Path

from autofram.agent import run_agent
from autofram.logger_out import log_error, logs_dir, truncate_for_display

log = logging.getLogger(__name__)


def contracts_dir():
    return Path.cwd() / "contracts"


def contracts_completed_dir():
    return Path.cwd() / "contracts_completed"


class Contracts:
    @staticmethod
    def _parse_title(text):
        match = re.search(r"^# (.+)$", text, re.MULTILINE)
        if match:
            return match.group(1).strip()
        for line in text.splitlines():
            if line.strip():
                return line.strip()
        return "empty"

    @staticmethod
    def _is_pending(text):
        return bool(re.search(r"^pending\s*$", text, re.MULTILINE))

    @staticmethod
    def _find_pending():
        cdir = contracts_dir()
        if not cdir.exists():
            return []
        return [p for p in sorted(cdir.glob("*.md")) if Contracts._is_pending(p.read_text())]

    async def execute(self, path):
        path = Path(path)
        text = path.read_text()
        title = Contracts._parse_title(text)
        log.info("Executing contract: %s", title)

        prompt = f"Contract file: {path.resolve()}\n\n{text}"

        try:
            last_content = await run_agent(title, prompt)

            dest = contracts_completed_dir()
            dest.mkdir(exist_ok=True)
            path.rename(dest / path.name)
            log.info("Contract completed: %s", title)
            return f"completed: {title}\nsummary: {last_content}"

        except Exception as e:
            stderr = getattr(e, "stderr", "")
            log.error("Contract failed: %s — %s", title, truncate_for_display(str(e)))
            if stderr:
                log.error("Contract stderr: %s", truncate_for_display(stderr))
            log_error(logs_dir() / "errors.log", f"Contract failed: {title} — {e}\nstderr: {stderr}")
            return f"failed: {title} — {e}"

    async def execute_all(self):
        pending = Contracts._find_pending()
        if not pending:
            return "No pending contracts found."

        results = []
        for path in pending:
            results.append(await self.execute(path))

        summary = f"Executed {len(results)} contract(s):\n"
        summary += "\n".join(f"- {r}" for r in results)
        return summary
