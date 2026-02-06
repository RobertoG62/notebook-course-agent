"""Phase 1: Extract answers from NotebookLM via browser automation skill."""

import subprocess
import time
import re
from pathlib import Path


class NotebookExtractor:
    """Query NotebookLM and save raw answers to files."""

    def __init__(self, config: dict):
        self.notebook_id = config["notebook"]["id"]
        self.skill_path = Path(config["notebook"]["skill_path"])
        self.delay = config["query"]["delay_seconds"]
        self.retries = config["query"]["retry_attempts"]
        self.timeout = config["query"]["timeout_seconds"]
        self.strip_marker = config["query"]["strip_suffix"]

    def extract_all(self, questions: list, output_dir: Path) -> dict:
        """Run all questions and save answers. Returns {q_id: {success, file, chars}}."""
        results = {}
        total = len(questions)

        for i, q in enumerate(questions, 1):
            q_id = q["id"]
            text = q["text"]
            print(f"\n  [{i}/{total}] {q_id}: {text[:70]}...")

            answer = self._query(text)

            if answer is None and self.retries > 0:
                print(f"    Retrying...")
                time.sleep(5)
                answer = self._query(text)

            if answer:
                answer = self._clean_answer(answer)
                out_file = output_dir / f"{q_id}.txt"
                out_file.write_text(answer, encoding="utf-8")
                print(f"    Saved {out_file.name} ({len(answer)} chars)")
                results[q_id] = {"success": True, "file": out_file, "chars": len(answer)}
            else:
                print(f"    FAILED - skipping")
                results[q_id] = {"success": False}

            if i < total:
                print(f"    Waiting {self.delay}s...")
                time.sleep(self.delay)

        return results

    def _query(self, question: str) -> str | None:
        """Run a single NotebookLM query via subprocess."""
        # Escape double quotes in question
        escaped_q = question.replace('"', '\\"')

        cmd = (
            f'cmd /c "cd /d "{self.skill_path}" && '
            f"set PYTHONIOENCODING=utf-8 && "
            f'.venv\\Scripts\\python.exe scripts\\run.py ask_question.py '
            f'--question "{escaped_q}" '
            f'--notebook-id "{self.notebook_id}""'
        )

        try:
            result = subprocess.run(
                cmd, shell=True, capture_output=True, text=True,
                timeout=self.timeout, encoding="utf-8"
            )
            if result.returncode == 0:
                return self._extract_answer(result.stdout)
            else:
                print(f"    Error: {result.stderr[:200]}")
                return None
        except subprocess.TimeoutExpired:
            print(f"    Timeout ({self.timeout}s)")
            return None
        except Exception as e:
            print(f"    Exception: {e}")
            return None

    def _extract_answer(self, output: str) -> str | None:
        """Extract the answer text between the two === dividers."""
        # Split on ========== lines
        parts = re.split(r"={10,}", output)
        # The answer is in the 3rd part (after header, after Question line)
        if len(parts) >= 3:
            return parts[2].strip()
        # Fallback: try to find content after "Got answer!"
        match = re.search(r"Got answer!\s*\n(.*)", output, re.DOTALL)
        if match:
            return match.group(1).strip()
        return None

    def _clean_answer(self, text: str) -> str:
        """Remove the trailing follow-up reminder."""
        idx = text.find(self.strip_marker)
        if idx != -1:
            text = text[:idx].strip()
        # Also remove trailing === dividers
        text = re.sub(r"\n={10,}\s*$", "", text)
        return text
