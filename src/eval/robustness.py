"""Perturbation-based robustness scoring."""

from __future__ import annotations

import random
from difflib import SequenceMatcher
from typing import Callable, Dict, List


class PerturbationSuite:
    """Apply lightweight text perturbations to approximate robustness."""

    def __init__(self, seed: int = 0) -> None:
        random.seed(seed)
        self.transforms: List[tuple[str, Callable[[str], str]]] = [
            ("drop_vowels", self._drop_vowels),
            ("uppercase", lambda text: text.upper()),
            ("shuffle_words", self._shuffle_words),
        ]

    def score(self, text: str) -> Dict[str, float | List[Dict[str, float]]]:
        if not text.strip():
            return {"consistency": 0.0, "cases": []}
        cases = []
        scores = []
        for name, transform in self.transforms:
            mutated = transform(text)
            similarity = SequenceMatcher(None, text, mutated).ratio()
            scores.append(similarity)
            cases.append({"transform": name, "similarity": round(similarity, 3)})
        return {"consistency": sum(scores) / len(scores), "cases": cases}

    def _drop_vowels(self, text: str) -> str:
        return "".join(ch for ch in text if ch.lower() not in "aeiou")

    def _shuffle_words(self, text: str) -> str:
        words = text.split()
        random.shuffle(words)
        return " ".join(words)
