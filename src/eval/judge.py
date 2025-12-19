"""LLM-as-a-judge scaffolding."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from rich.console import Console

try:  # pragma: no cover - optional dependency
    from langchain.llms.fake import FakeListLLM
except Exception:  # pragma: no cover
    FakeListLLM = None  # type: ignore

console = Console()


class LLMJudge:
    """Use a stronger LLM (or fake stand-in) to grade responses."""

    def __init__(self, model_name: str = "gpt-4o-mini", output_path: Path = Path("data/metrics/judge.jsonl")) -> None:
        self.model_name = model_name
        self.output_path = output_path
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        self.fake_llm = FakeListLLM(responses=["ACCEPT", "SAFE"]) if FakeListLLM else None

    def score(self, prompt: str, response: str, requirements: str) -> Dict[str, Any]:
        if self.fake_llm:
            _ = self.fake_llm(prompt)  # consume fake response
            verdict = "ACCEPT"
        else:
            verdict = "ACCEPT" if response and requirements.lower() in response.lower() else "REVIEW"
        metrics = {
            "model": self.model_name,
            "verdict": verdict,
            "prompt": prompt[:120],
            "requirements": requirements,
        }
        self._log(metrics, response)
        return metrics

    def _log(self, metrics: Dict[str, Any], response: str) -> None:
        record = {**metrics, "response_snippet": response[:200]}
        with self.output_path.open("a", encoding="utf-8") as fout:
            fout.write(json.dumps(record) + "\n")
