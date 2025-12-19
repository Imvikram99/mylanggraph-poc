"""Adversarial testing helpers."""

from __future__ import annotations

from typing import Dict, List

from scripts.eval.adversarial_catalog import ADVERSARIAL_CASES


class AdversarialTester:
    def __init__(self, cases: List[Dict[str, str]] | None = None) -> None:
        self.cases = cases or ADVERSARIAL_CASES

    def scan_output(self, text: str) -> List[Dict[str, str]]:
        """Return adversarial signatures that appear in the output."""
        text_lower = text.lower()
        hits: List[Dict[str, str]] = []
        for case in self.cases:
            for signature in case.get("signatures", []):
                if signature.lower() in text_lower:
                    hits.append({"name": case["name"], "category": case["category"], "signature": signature})
                    break
        return hits

    def catalog(self) -> List[Dict[str, str]]:
        return self.cases
